"""
sync_invoices.py
==================
Composition Root para la sincronizacion de facturas de compra.
Punto de entrada unico desde la UI y API.
Crea los adapters y los inyecta al caso de uso.

Mantiene compatibilidad con el patron existente en resources/utils/pagination.py
mediante el re-export en uses_cases/sales_invoices/sync_by_supplier.py
"""

import frappe
from datetime import datetime
from qp_supplier_front.uses_cases.purchase_invoice.sync_core import (
    sync_invoices,
    sync_all_invoices,
)
from qp_supplier_front.infrastructure.adapters.fetch_adapter import (
    fetch_invoices,
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


@frappe.whitelist()
def sync_by_supplier(supplier_id, flow="GP"):
    now = str(datetime.now())
    try:
        synced_count = sync_invoices(
            supplier_id=supplier_id,
            flow=flow,
            fetch_fn=fetch_invoices,
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
    try:
        synced_count = sync_all_invoices(
            flow=flow,
            fetch_fn=fetch_invoices,
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
            title="Error sync all purchase invoices ({})".format(flow),
        )
        return {
            "success": False,
            "error": str(e),
        }

