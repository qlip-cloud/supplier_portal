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
    get_log_company_tax_id,
    create_document_detail,
    log_sync_attempt,
    mark_line_completed,
)
from qp_supplier_front.services import sync_lock
from qp_authorization.use_case.basic.authorize import send_request_status
from qp_supplier_front.resources.documenteme.auto_assign import run_auto_assign
from qp_supplier_front.resources.documenteme.auto_approve import run_auto_approve
from qp_supplier_front.resources.documenteme.auto_reject import run_auto_reject

DOCUMENTS_LOCK_DOMAIN = "documents"


def get_company_tax_id(company_name):
    return frappe.get_doc("Company", company_name).tax_id


def run_documenteme_auto_assign(doc_names=None):
    try:
        run_auto_assign(doc_names=doc_names)
        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme auto_assign sync_all")


def run_documenteme_auto_reject(doc_names=None):
    try:
        result = run_auto_reject(enqueue=False, doc_names=doc_names)
        frappe.db.commit()
        return result

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme auto_reject sync_all")
        return None


def run_documenteme_auto_approve(doc_names=None):
    try:
        result = run_auto_approve(enqueue=False, doc_names=doc_names)
        frappe.db.commit()
        return result

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme auto_approve sync_all")
        return None


@frappe.whitelist()
def sync_all(nvfac_esta=None, nvfac_fini=None, nvfac_ffin=None):
    nvfac_fini = nvfac_fini if nvfac_fini is not None else get_default_nvfac_fini()
    nvfac_ffin = nvfac_ffin if nvfac_ffin is not None else get_default_nvfac_ffin()

    if not sync_lock.acquire(DOCUMENTS_LOCK_DOMAIN):
        return {
            "success": False,
            "skipped": True,
            "error": "Ya hay una sincronización en curso",
        }

    try:
        companies = frappe.get_all("Company", pluck="name")

        for company_id in companies:
            sync_by_supplier(
                supplier_id=company_id,
                get_tax_id_fn=get_company_tax_id,
                send_request_fn=send_request_status,
                create_log_fn=create_sync_log,
                create_lines_fn=create_sync_lines,
                commit_fn=lambda: frappe.db.commit(),
                nvfac_esta=nvfac_esta,
                nvfac_fini=nvfac_fini,
                nvfac_ffin=nvfac_ffin,
            )

        created_names = sync_detail(
            get_uncompleted_lines_fn=get_uncompleted_lines,
            send_request_fn=send_request_status,
            create_document_detail_fn=create_document_detail,
            log_sync_attempt_fn=log_sync_attempt,
            mark_line_completed_fn=mark_line_completed,
            commit_fn=lambda: frappe.db.commit(),
            get_company_tax_id_fn=get_log_company_tax_id,
        )

        run_documenteme_auto_assign(created_names)
        reject_result = run_documenteme_auto_reject(created_names)
        approve_result = run_documenteme_auto_approve(created_names)

        return {
            "success": True,
            "companies_count": len(companies),
            "created_count": len(created_names or []),
            "rejected": (reject_result or {}).get("rejected") or [],
            "approved": (approve_result or {}).get("approved") or [],
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "sync_all")
        return {"success": False, "error": "Internal error"}
    finally:
        sync_lock.release(DOCUMENTS_LOCK_DOMAIN)