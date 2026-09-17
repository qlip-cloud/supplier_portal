"""
sync_by_supplier.py (payment_receipt)
======================================
Wrappers @frappe.whitelist() para la sincronizacion de recibos de pago.

El flujo automatico/general (full manual + cron 5 min) se hace por
VENTANAS DE FECHAS GLOBALES (sin filtro de proveedores) usando el backend
configurado en qp_SP_MasterSetup.documenteme_backend (GP o BC).

NOTA PENDIENTE: la sincronizacion GP queda pendiente de revision; por ahora
GP solo se sincroniza por proveedor al visitar el portal (sync_by_supplier).

Puntos de entrada:
  - sync_by_supplier(supplier_id, flow) -> sync por proveedor (portal, GP+BC)
  - sync_all(flow)                       -> full general (global windows)
  - sync_full(flow)                      -> full general (background)
  - sync_incremental(flow)               -> solo dia actual (global window)

El flujo automatico usa el backend configurado en
qp_SP_MasterSetup.documenteme_backend (GP o BC). Si se pasa un flow
explicito, se respeta ese valor.
"""

import frappe
from datetime import datetime
from qp_supplier_front.uses_cases.payment_receipt.sync_core import (
    sync_payments_window,
)
from qp_supplier_front.infrastructure.adapters.fetch_adapter import (
    fetch_invoices as fetch_bearer,
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
    today_start,
)
from qp_supplier_front.services.sync_lock import acquire, release, wait_for


FETCH_MAP = {
    "GP": fetch_bearer,
    "BC": fetch_oauth,
}

SYNC_TYPE = "Receipt"
SYNC_DOMAIN = "receipts"
CHECKPOINT_FIELD = "receipts_date_sync"


def _get_checkpoint_start(today):
    checkpoint = frappe.db.get_single_value("qp_SP_MasterSetup", CHECKPOINT_FIELD)
    return compute_sync_start(checkpoint, today)


def _advance_checkpoint(w_end):
    try:
        frappe.db.set_value("qp_SP_MasterSetup", None, CHECKPOINT_FIELD, w_end)
        commit()
    except Exception:
        pass


def _run_supplier(supplier_id, flow, mode):
    strategy = get_payment_strategy(flow)
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    today = datetime.now()

    if mode == "incremental":
        start = today_start(today)
    else:
        last_date = get_last_creation(
            strategy["doctype"],
            supplier_id,
            strategy["db_fields"]["order_field"],
        )
        start = compute_sync_start(last_date, today)

    total_inserted = 0
    windows_count = 0

    for w_start, w_end in generate_date_windows(start, today):
        windows_count += 1
        log_fn = build_sync_log_fn(
            SYNC_TYPE,
            supplier_id,
            flow,
            mode,
            today,
            track_in_progress=(mode == "full"),
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


def _run_global(flow, mode):
    if flow == "GP":
        return _run_global_gp(mode)
    strategy = get_payment_strategy(flow)
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    today = datetime.now()

    if mode == "incremental":
        start = today_start(today)
    else:
        start = _get_checkpoint_start(today)

    total_inserted = 0
    windows_count = 0

    for w_start, w_end in generate_date_windows(start, today):
        windows_count += 1
        log_fn = build_sync_log_fn(
            SYNC_TYPE,
            None,
            flow,
            mode,
            today,
            track_in_progress=(mode == "full"),
        )
        try:
            result = sync_payments_window(
                supplier_id=None,
                flow=flow,
                window_start=w_start,
                window_end=w_end,
                fetch_fn=fetch_fn,
                existing_ids_fn=get_existing_ids,
                commit_fn=commit,
                log_sync_fn=log_fn,
                now=str(today),
                scope="global",
            )
            total_inserted += result["inserted"]
        except Exception as e:
            rollback()
            _safe_log_error(log_fn, w_start, w_end, str(e))
            commit()
            raise
        _advance_checkpoint(w_end)

    return {
        "inserted": total_inserted,
        "windows": windows_count,
    }


def _run_global_gp(mode):
    """
    Flujo automatico GP: la estrategia GP de recibos no tiene sincronizacion
    global por ventanas (solo por proveedor). Se itera todos los proveedores
    con el mismo flujo per-supplier del portal.
    """
    suppliers = frappe.db.get_list("Supplier", pluck="name")
    total_inserted = 0
    for supplier_id in suppliers:
        try:
            result = _run_supplier(supplier_id, "GP", mode)
            total_inserted += result["inserted"]
        except Exception as e:
            rollback()
            log_error(
                message=str(e),
                title="Error sync all payment receipts (GP): {}".format(supplier_id),
            )
    return {
        "inserted": total_inserted,
        "windows": 0,
    }


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


@frappe.whitelist()
def sync_by_supplier(supplier_id, flow="GP"):
    if not acquire(SYNC_DOMAIN):
        return {
            "success": True,
            "synced_count": 0,
            "windows": 0,
            "skipped": True,
        }
    try:
        result = _run_supplier(supplier_id, flow, "full")
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
        release(SYNC_DOMAIN)


@frappe.whitelist()
def sync_all(flow=None):
    flow = resolve_flow(flow)
    if not acquire(SYNC_DOMAIN):
        return {"success": True, "skipped": True}
    try:
        result = _run_global(flow, "full")
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
            title="Error sync all payment receipts ({})".format(flow),
        )
        return {
            "success": False,
            "error": str(e),
            "skipped": False,
        }
    finally:
        release(SYNC_DOMAIN)


@frappe.whitelist()
def sync_full(flow=None):
    flow = resolve_flow(flow)
    frappe.enqueue(
        "qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier.sync_full_job",
        flow=flow,
        #now=True,
        queue="long",
        timeout=14400,
        job_name="sync full payment receipts",
    )
    return {"success": True, "enqueued": True}


def sync_full_job(flow="BC"):
    flow = resolve_flow(flow)
    #if not acquire(SYNC_DOMAIN):
    #    if not wait_for(SYNC_DOMAIN, timeout=300):
    #        log_error(
    #            message="No se pudo adquirir el lock de sincronizacion",
    #            title="sync full payment receipts",
    #        )
    #        return
    try:
        _run_global(flow, "full")
    finally:
        release(SYNC_DOMAIN)


@frappe.whitelist()
def sync_incremental(flow=None):
    flow = resolve_flow(flow)
    if not acquire(SYNC_DOMAIN):
        return {"success": True, "skipped": True}
    try:
        _run_global(flow, "incremental")
    finally:
        release(SYNC_DOMAIN)
    return {"success": True, "skipped": False}
