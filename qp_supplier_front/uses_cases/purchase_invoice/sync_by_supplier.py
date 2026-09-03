"""
sync_by_supplier.py (purchase_invoice)
========================================
Wrappers @frappe.whitelist() para la sincronizacion de facturas de compra.

El flujo automatico/general (full manual + cron 5 min) esta restringido
a BC y se hace por VENTANAS DE FECHAS GLOBALES (sin filtro de proveedores).

NOTA PENDIENTE: la sincronizacion GP queda pendiente de revision; por ahora
GP solo se sincroniza por proveedor al visitar el portal (sync_by_supplier).

Puntos de entrada:
  - sync_by_supplier(supplier_id, flow) -> sync por proveedor (portal, GP+BC)
  - sync_all(flow)                       -> full general BC (global windows)
  - sync_all_suppliers(flow)             -> alias legacy (BC)
  - sync_full(flow)                      -> full general BC (background)
  - sync_incremental(flow)               -> solo dia actual BC (global window)
  - scheduled_sync_bc()                  -> cron diario BC (incremental)
"""

import frappe
from datetime import datetime
from qp_supplier_front.uses_cases.purchase_invoice.sync_core import (
    sync_invoices_window,
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
from qp_supplier_front.infrastructure.strategies.registry import get_strategy
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

SYNC_TYPE = "Invoice"
SYNC_DOMAIN = "invoices"
CHECKPOINT_FIELD = "invoices_date_sync"


def _get_checkpoint_start(today):
    checkpoint = frappe.db.get_single_value("qp_SP_MasterSetup", CHECKPOINT_FIELD)
    return compute_sync_start(checkpoint, today)


def _advance_checkpoint(w_end):
    try:
        frappe.db.set_value("qp_SP_MasterSetup", None, CHECKPOINT_FIELD, w_end)
        commit()
    except Exception:
        pass


def _log_skipped(skip):
    frappe.log_error(
        message="Document_No={doc_no}, Entry_No={entry}, Vendor_No={vendor}, "
                "LHCOrdenCompra='{value}' ({length} chars)".format(
                    doc_no=skip.get("Document_No"),
                    entry=skip.get("Entry_No"),
                    vendor=skip.get("Vendor_No"),
                    value=skip.get("LHCOrdenCompra"),
                    length=skip.get("length"),
                ),
        title="BC Sync - LHCOrdenCompra excede limite",
    )


def _run_supplier(supplier_id, flow, mode):
    strategy = get_strategy(flow)
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
            result = sync_invoices_window(
                supplier_id=supplier_id,
                flow=flow,
                window_start=w_start,
                window_end=w_end,
                fetch_fn=fetch_fn,
                existing_ids_fn=get_existing_ids,
                commit_fn=commit,
                log_sync_fn=log_fn,
                now=str(today),
                log_skipped_fn=_log_skipped,
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
    strategy = get_strategy(flow)
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
            result = sync_invoices_window(
                supplier_id=None,
                flow=flow,
                window_start=w_start,
                window_end=w_end,
                fetch_fn=fetch_fn,
                existing_ids_fn=get_existing_ids,
                commit_fn=commit,
                log_sync_fn=log_fn,
                now=str(today),
                log_skipped_fn=_log_skipped,
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
            title="Error sync purchase invoice: {} ({})".format(
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
def sync_all(flow="BC"):
    if not acquire(SYNC_DOMAIN):
        return {"success": True, "synced_count": 0, "skipped": True}
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
            title="Error sync all purchase invoices ({})".format(flow),
        )
        return {
            "success": False,
            "error": str(e),
            "skipped": False,
        }
    finally:
        release(SYNC_DOMAIN)


@frappe.whitelist()
def sync_all_suppliers(flow="BC"):
    return sync_all(flow=flow)


@frappe.whitelist()
def sync_full(flow="BC"):
    frappe.enqueue(
        "qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier.sync_full_job",
        flow=flow,
        queue="long",
        timeout=14400,
        job_name="sync full purchase invoices",
    )
    return {"success": True, "enqueued": True}


def sync_full_job(flow="BC"):
    if not acquire(SYNC_DOMAIN):
        if not wait_for(SYNC_DOMAIN, timeout=300):
            log_error(
                message="No se pudo adquirir el lock de sincronizacion",
                title="sync full purchase invoices",
            )
            return
    try:
        _run_global(flow, "full")
    finally:
        release(SYNC_DOMAIN)


@frappe.whitelist()
def sync_incremental(flow="BC"):
    if not acquire(SYNC_DOMAIN):
        return {"success": True, "skipped": True}
    try:
        _run_global(flow, "incremental")
    finally:
        release(SYNC_DOMAIN)
    return {"success": True, "skipped": False}


def scheduled_sync_bc():
    return sync_incremental(flow="BC")
