"""
sync_by_supplier.py (payment_receipt)
======================================
Sincronizacion de recibos de pago BAJO DEMANDA por proveedor, con
checkpoint por proveedor en el campo Supplier.qp_receipts_last_sync.

Estrategias:
  - sync_by_supplier : on-demand (portal). Resuelve la fecha de inicio:
      1. supplier.qp_receipts_last_sync
      2. ultima fecha en qp_SP_PaymentReceipt del proveedor
      3. qp_SP_MasterSetup.initial_sync_date (default 2024-01-01)
      Al finalizar con exito actualiza el checkpoint a NOW().
  - sync_full (cron fines de semana) : proveedores SIN checkpoint, desde
      initial_sync_date hasta NOW(); actualiza el checkpoint al terminar.
  - sync_incremental (cron diario 00:00) : proveedores CON checkpoint,
      desde el checkpoint hasta NOW(); actualiza al terminar.

Reglas:
  - Si un proveedor falla, NO se actualiza su checkpoint y el error queda
    en qp_SP_SyncLog (ventana Error) + Error Log.
  - Idempotente: get_existing_ids descarta recibos ya insertados.
  - Lock por proveedor (lease con dueño + heartbeat + stale-steal), para que
    full e incremental no colisionen sobre el mismo proveedor y un sync
    fallido se desbloquee solo (TTL corto renovado por heartbeat).
"""

import frappe
from datetime import datetime

from qp_supplier_front.uses_cases.payment_receipt.sync_core import (
    sync_payments_window,
)
from qp_supplier_front.infrastructure.adapters.fetch_adapter import (
    fetch_invoices as fetch_bearer,
    fetch_payment_receipts,
)
from qp_supplier_front.infrastructure.adapters.fetch_oauth_adapter import (
    fetch_invoices as fetch_oauth,
)
from qp_supplier_front.infrastructure.adapters.filter_adapter import (
    get_last_creation,
    get_existing_ids,
)
from qp_supplier_front.infrastructure.adapters.commit_adapter import (
    commit,
    rollback,
    log_error,
)
from qp_supplier_front.infrastructure.adapters.log_adapter import build_sync_log_fn
from qp_supplier_front.infrastructure.strategies.registry import (
    get_payment_strategy,
)
from qp_supplier_front.services.flow_config import resolve_flow
from qp_supplier_front.services.sync_window import (
    compute_sync_start,
    generate_date_windows,
    resolve_on_demand_start,
)
from qp_supplier_front.services.sync_checkpoint import (
    get_initial_sync_date,
    get_checkpoint,
    set_checkpoint,
    suppliers_without_checkpoint,
    suppliers_with_checkpoint,
)
from qp_supplier_front.services.sync_lock import (
    acquire,
    release,
    heartbeat,
)


FETCH_MAP = {
    "GP": fetch_payment_receipts,
    "BC": fetch_oauth,
}

SYNC_TYPE = "Receipt"
SYNC_DOMAIN = "receipts"
CHECKPOINT_FIELD = "qp_receipts_last_sync"


def _supplier_domain(supplier_id):
    return "{}:{}".format(SYNC_DOMAIN, supplier_id)


def _resolve_start(supplier_id, flow, mode, today):
    """Fecha de inicio segun la estrategia (full/incremental/on_demand)."""
    strategy = get_payment_strategy(flow)
    initial = get_initial_sync_date()

    if mode == "incremental":
        return compute_sync_start(
            get_checkpoint(supplier_id, CHECKPOINT_FIELD),
            today,
            historical_start=initial,
        )
    if mode == "full":
        return compute_sync_start(None, today, historical_start=initial)

    checkpoint = get_checkpoint(supplier_id, CHECKPOINT_FIELD)
    last_receipt = None
    if not checkpoint:
        last_receipt = get_last_creation(
            strategy["doctype"],
            supplier_id,
            strategy["db_fields"]["order_field"],
        )
    return resolve_on_demand_start(checkpoint, last_receipt, initial, today)


def _safe_log_error(log_fn, w_start, w_end, error):
    try:
        log_fn(
            status="Error",
            window_start=w_start,
            window_end=w_end,
            error_message=error,
        )
    except Exception:
        pass


def _run_supplier(
    supplier_id,
    flow,
    mode,
    today,
    lock_domain=None,
    lock_token=None,
):
    """Ejecuta el sync por ventanas para un proveedor. Reanima el lease (heartbeat)
    entre ventanas. No toca el checkpoint: eso lo decide el caller si todo fue ok."""
    strategy = get_payment_strategy(flow)
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    start = _resolve_start(supplier_id, flow, mode, today)

    total_inserted = 0
    windows_count = 0
    track_in_progress = mode in ("full", "on_demand")

    for w_start, w_end in generate_date_windows(start, today):
        windows_count += 1
        if lock_domain and lock_token:
            heartbeat(lock_domain, lock_token)

        log_fn = build_sync_log_fn(
            SYNC_TYPE,
            supplier_id,
            flow,
            mode,
            today,
            track_in_progress=track_in_progress,
        )
        try:
            result = sync_payments_window(
                supplier_id=supplier_id,
                flow=flow,
                window_start=w_start,
                window_end=w_end,
                fetch_fn=fetch_fn,
                existing_ids_fn=get_existing_ids,
                commit_fn=commit,
                log_sync_fn=log_fn,
                now=str(today),
            )
            total_inserted += result["inserted"]
        except Exception as e:
            rollback()
            _safe_log_error(log_fn, w_start, w_end, str(e))
            commit()
            raise

    return {
        "inserted": total_inserted,
        "windows": windows_count,
    }


def _sweep(flow, supplier_ids, mode):
    """Barrido por proveedor con lock individual y checkpoint por proveedor."""
    today = datetime.now()
    total_inserted = 0
    ok = 0
    failed = 0

    for supplier_id in supplier_ids:
        supplier_domain = _supplier_domain(supplier_id)
        lock = acquire(supplier_domain)
        if lock is None:
            continue
        token = lock["token"]
        try:
            result = _run_supplier(
                supplier_id,
                flow,
                mode,
                today,
                supplier_domain,
                token,
            )
            set_checkpoint(supplier_id, CHECKPOINT_FIELD, str(today))
            total_inserted += result["inserted"]
            ok += 1
        except Exception as e:
            rollback()
            log_error(
                message=str(e),
                title="Error sync payment receipts: {} ({})".format(
                    supplier_id, flow
                ),
            )
            failed += 1
        finally:
            release(supplier_domain, token)

    return {
        "success": True,
        "inserted": total_inserted,
        "ok": ok,
        "failed": failed,
    }


@frappe.whitelist()
def sync_by_supplier(supplier_id, flow="GP"):
    """On-demand (portal): sincroniza un proveedor desde el checkpoint/recibos
    previos/fecha inicial hasta ahora. Actualiza el checkpoint si todo ok."""
    supplier_domain = _supplier_domain(supplier_id)
    lock = acquire(supplier_domain)
    if lock is None:
        return {
            "success": True,
            "synced_count": 0,
            "windows": 0,
            "skipped": True,
        }
    token = lock["token"]
    today = datetime.now()
    try:
        result = _run_supplier(
            supplier_id,
            flow,
            "on_demand",
            today,
            supplier_domain,
            token,
        )
        set_checkpoint(supplier_id, CHECKPOINT_FIELD, str(today))
        return {
            "success": True,
            "synced_count": result["inserted"],
            "windows": result["windows"],
            "skipped": False,
        }
    except Exception as e:
        rollback()
        log_error(
            message=frappe.get_traceback(),
            title="Error sync payment receipt: {} ({})".format(
                supplier_id, flow
            ),
        )
        return {
            "success": False,
            "error": str(e),
            "skipped": False,
        }
    finally:
        release(supplier_domain, token)


@frappe.whitelist()
def sync_full(flow=None):
    """Full por lotes (cron fin de semana): proveedores SIN checkpoint desde
    la fecha inicial global. Aqui solo se programa; el trabajo corre en
    segundo plano."""
    flow = resolve_flow(flow)
    frappe.enqueue(
        "qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier.sync_full_job",
        flow=flow,
        queue="long",
        timeout=14400,
        job_name="sync full payment receipts",
    )
    return {"success": True, "enqueued": True}


def sync_full_job(flow=None):
    flow = resolve_flow(flow)
    return _sweep(flow, suppliers_without_checkpoint(CHECKPOINT_FIELD), "full")


@frappe.whitelist()
def sync_incremental(flow=None):
    """Delta diario (cron 00:00): proveedores CON checkpoint, desde su
    checkpoint hasta ahora."""
    flow = resolve_flow(flow)
    return _sweep(flow, suppliers_with_checkpoint(CHECKPOINT_FIELD), "incremental")


@frappe.whitelist()
def sync_all(flow=None):
    """Alias legacy del full por lotes."""
    return sync_full(flow=flow)