import frappe
from qp_supplier_front.uses_cases.documents.sync_by_supplier import (
    sync_by_supplier,
    get_default_nvfac_fini,
    get_default_nvfac_ffin,
)
from qp_supplier_front.uses_cases.documents.sync_detail import sync_detail
from qp_supplier_front.services.document_sync import (
    create_sync_log,
    create_sync_lines,
    get_uncompleted_lines,
    create_document_detail,
    log_sync_attempt,
    mark_line_completed,
)
from qp_authorization.use_case.basic.authorize import send_request_status


def get_supplier_tax_id(supplier_name):
    return frappe.get_doc("Supplier", supplier_name).tax_id


@frappe.whitelist()
def sync_all(nvfac_esta=None, nvfac_fini=None, nvfac_ffin=None):
    nvfac_fini = nvfac_fini if nvfac_fini is not None else get_default_nvfac_fini()
    nvfac_ffin = nvfac_ffin if nvfac_ffin is not None else get_default_nvfac_ffin()
    try:
        suppliers = frappe.get_all("Supplier", pluck="name")

        for supplier_id in suppliers:
            sync_by_supplier(
                supplier_id=supplier_id,
                get_tax_id_fn=get_supplier_tax_id,
                send_request_fn=send_request_status,
                create_log_fn=create_sync_log,
                create_lines_fn=create_sync_lines,
                commit_fn=lambda: frappe.db.commit(),
                nvfac_esta=nvfac_esta,
                nvfac_fini=nvfac_fini,
                nvfac_ffin=nvfac_ffin,
            )

        sync_detail(
            get_uncompleted_lines_fn=get_uncompleted_lines,
            send_request_fn=send_request_status,
            create_document_detail_fn=create_document_detail,
            log_sync_attempt_fn=log_sync_attempt,
            mark_line_completed_fn=mark_line_completed,
            commit_fn=lambda: frappe.db.commit(),
        )

        return {"success": True, "suppliers_count": len(suppliers)}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "sync_all")
        return {"success": False, "error": "Internal error"}
