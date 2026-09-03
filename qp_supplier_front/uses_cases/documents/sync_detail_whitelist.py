import frappe
from qp_supplier_front.uses_cases.documents.sync_detail import sync_detail
from qp_supplier_front.services.document_sync import (
    get_uncompleted_lines,
    get_log_company_tax_id,
    create_document_detail,
    log_sync_attempt,
    mark_line_completed,
)
from qp_authorization.use_case.basic.authorize import send_request_status


@frappe.whitelist()
def sync_detail_whitelist():
    try:
        sync_detail(
            get_uncompleted_lines_fn=get_uncompleted_lines,
            send_request_fn=send_request_status,
            create_document_detail_fn=create_document_detail,
            log_sync_attempt_fn=log_sync_attempt,
            mark_line_completed_fn=mark_line_completed,
            commit_fn=lambda: frappe.db.commit(),
            get_company_tax_id_fn=get_log_company_tax_id,
        )
        return {"success": True}
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "sync_detail")
        return {"success": False, "error": "Internal error"}
