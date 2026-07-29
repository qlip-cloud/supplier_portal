"""
sync_by_supplier.py
====================
Wrapper delgado @frappe.whitelist() para sincronizacion de facturas.
Inyecta las implementaciones reales (Frappe DB, API) al nucleo puro.

Punto de entrada unico:
  - sync_by_supplier(supplier_id, flow)  -> per-supplier
  - sync_all(flow)                       -> full sync
"""

import frappe
from datetime import datetime
from qp_supplier_front.uses_cases.purchase_invoice.sync_core import (
    sync_invoices,
    sync_all_invoices,
    sync_all_suppliers_invoices,
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
    get_bc_suppliers,
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


@frappe.whitelist()
def sync_by_supplier(supplier_id, flow="GP"):
    now = str(datetime.now())
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    try:
        synced_count = sync_invoices(
            supplier_id=supplier_id,
            flow=flow,
            fetch_fn=fetch_fn,
            last_creation_fn=get_last_creation,
            existing_ids_fn=get_existing_ids,
            commit_fn=commit,
            now=now,
            log_skipped_fn=_log_skipped,
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
            title="Error sync purchase invoice: {} ({})".format(
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
        synced_count = sync_all_invoices(
            flow=flow,
            fetch_fn=fetch_fn,
            existing_ids_fn=get_existing_ids,
            commit_fn=commit,
            now=now,
            log_skipped_fn=_log_skipped,
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
            title="Error sync all purchase invoices ({})".format(flow),
        )
        return {
            "success": False,
            "error": str(e),
        }


@frappe.whitelist()
def sync_all_suppliers(flow="BC"):
    now = str(datetime.now())
    fetch_fn = FETCH_MAP.get(flow, fetch_bearer)
    try:
        result = sync_all_suppliers_invoices(
            flow=flow,
            fetch_fn=fetch_fn,
            get_suppliers_fn=get_bc_suppliers,
            last_creation_fn=get_last_creation,
            existing_ids_fn=get_existing_ids,
            commit_fn=commit,
            log_error_fn=log_error,
            now=now,
            log_skipped_fn=_log_skipped,
        )
        return {
            "success": True,
            "synced_count": result["synced_count"],
            "errors": result["errors"],
        }
    except Exception as e:
        log_error(
            message=frappe.get_traceback(),
            title="Error sync all suppliers invoices ({})".format(flow),
        )
        return {
            "success": False,
            "error": str(e),
        }


def scheduled_sync_bc():
    return sync_all_suppliers(flow="BC")

