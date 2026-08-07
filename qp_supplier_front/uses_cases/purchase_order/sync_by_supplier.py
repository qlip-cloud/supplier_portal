"""
sync_by_supplier.py (purchase_order)
======================================
Wrappers @frappe.whitelist() para la sincronizacion de ordenes de compra.

NOTA PENDIENTE: las ordenes solo existen en GP y su sincronizacion queda
pendiente de revision. Por ahora se sincronizan SOLO por proveedor al
visitar el portal (sync_by_supplier / handler), sin flujo automatico general.

Puntos de entrada:
  - sync_by_supplier(supplier_id)   -> sync de un proveedor (portal)
  - handler(supplier_id)            -> alias legacy (paginacion, www)
"""

import frappe
from datetime import datetime

from qp_supplier_front.uses_cases.purchase_order.sync_core import sync_orders_window
from qp_supplier_front.infrastructure.strategies.gp.order_strategy import ORDER_STRATEGY
from qp_supplier_front.infrastructure.adapters.fetch_adapter import (
    fetch_invoices as fetch_gp,
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
from qp_supplier_front.services.sync_window import (
    compute_sync_start,
    generate_date_windows,
)
from qp_supplier_front.services.sync_lock import acquire, release

SYNC_TYPE = "Order"
SYNC_DOMAIN = "orders"


def get_items():
    items = frappe.get_list("Item", fields=["item_code", "item_name"])
    return {item["item_code"]: item for item in items}


def get_company():
    return frappe.defaults.get_user_default("company")


def _run_supplier(supplier_id, items_valid=None):
    strategy = ORDER_STRATEGY
    today = datetime.now()

    last_date = get_last_creation(
        strategy["doctype"],
        supplier_id,
        strategy["db_fields"]["order_field"],
    )
    start = compute_sync_start(last_date, today)

    if items_valid is None:
        items_valid = get_items()

    total_inserted = 0
    windows_count = 0

    for w_start, w_end in generate_date_windows(start, today):
        windows_count += 1
        log_fn = build_sync_log_fn(
            SYNC_TYPE,
            supplier_id,
            "GP",
            "full",
            today,
            track_in_progress=True,
        )
        try:
            result = sync_orders_window(
                supplier_id=supplier_id,
                window_start=w_start,
                window_end=w_end,
                now=str(today),
                strategy=strategy,
                fetch_fn=fetch_gp,
                existing_ids_fn=get_existing_ids,
                get_items_fn=lambda: items_valid,
                get_company_fn=get_company,
                commit_fn=commit,
                log_sync_fn=log_fn,
                log_error_fn=log_error,
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
        result = _run_supplier(supplier_id)
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
            title="Error sync purchase order: {} (GP)".format(supplier_id),
        )
        return {
            "success": False,
            "error": str(e),
            "skipped": False,
        }
    finally:
        release(SYNC_DOMAIN)


def handler(supplier_id):
    return sync_by_supplier(supplier_id, flow="GP")
