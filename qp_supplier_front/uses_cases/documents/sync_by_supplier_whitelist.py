import frappe
from qp_supplier_front.uses_cases.documents.sync_by_supplier import sync_by_supplier
from qp_supplier_front.services.document_sync import create_sync_log, create_sync_lines
from qp_authorization.use_case.basic.authorize import send_request_status


@frappe.whitelist()
def sync_by_supplier_whitelist(supplier_id, nvfac_esta=None, nvfac_fini=None, nvfac_ffin=None):
    try:
        log_name = sync_by_supplier(
            supplier_id=supplier_id,
            get_tax_id_fn=lambda sid: frappe.get_doc("Supplier", sid).tax_id,
            send_request_fn=send_request_status,
            create_log_fn=create_sync_log,
            create_lines_fn=create_sync_lines,
            commit_fn=lambda: frappe.db.commit(),
            nvfac_esta=nvfac_esta,
            nvfac_fini=nvfac_fini,
            nvfac_ffin=nvfac_ffin,
        )
        return {"success": True, "log_name": log_name}
    except frappe.DoesNotExistError:
        frappe.db.rollback()
        frappe.log_error(
            "Supplier not found: {}".format(supplier_id), "sync_by_supplier"
        )
        return {"success": False, "error": "Supplier not found"}
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "sync_by_supplier")
        return {"success": False, "error": "Internal error"}
