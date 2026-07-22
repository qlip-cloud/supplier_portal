"""
sync_by_supplier.py (payment_receipt)
======================================
Wrapper delgado @frappe.whitelist() para sincronizacion de recibos de pago.
Inyecta las implementaciones reales (Frappe DB, API) al nucleo puro.

Punto de entrada unico:
  - sync_by_supplier(supplier_id, flow)  -> per-supplier
  - sync_all(flow)                       -> full sync
"""

import frappe
from datetime import datetime
from qp_supplier_front.uses_cases.payment_receipt.sync_core import (
    sync_payments,
    sync_all_payments,
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
from qp_supplier_front.exception.sync import (
    ExceptionSyncNoNewRecords,
)


FETCH_MAP = {
    "GP": fetch_bearer,
    "BC": fetch_oauth,
}


@frappe.whitelist()
def sync_by_supplier(supplier_id, flow="GP"):
    now = str(datetime.now())
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    try:
        synced_count = sync_payments(
            supplier_id=supplier_id,
            flow=flow,
            fetch_fn=fetch_fn,
            last_creation_fn=get_last_creation,
            existing_ids_fn=get_existing_ids,
            commit_fn=commit,
            now=now,
        )
        return {
            "success": True,
            "synced_count": synced_count,
        }
    except ExceptionSyncNoNewRecords:
        return {
            "success": True,
            "synced_count": 0,
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
        }


@frappe.whitelist()
def sync_all(flow="GP"):
    now = str(datetime.now())
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    try:
        synced_count = sync_all_payments(
            flow=flow,
            fetch_fn=fetch_fn,
            existing_ids_fn=get_existing_ids,
            commit_fn=commit,
            now=now,
        )
        return {
            "success": True,
            "synced_count": synced_count,
        }
    except ExceptionSyncNoNewRecords:
        return {
            "success": True,
            "synced_count": 0,
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
        }
