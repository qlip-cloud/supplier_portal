from datetime import datetime, timedelta

import frappe
from qp_authorization.use_case.basic.authorize import send_request_status
from qp_supplier_front.services.document_sync import (
    create_document_detail,
    create_sync_lines,
    create_sync_log,
    get_uncompleted_lines,
    log_sync_attempt,
    mark_line_completed,
)
from qp_supplier_front.uses_cases.documents.sync_by_supplier import (
    sync_by_supplier,
)
from qp_supplier_front.uses_cases.documents.sync_detail import sync_detail


def get_supplier_tax_id(supplier_name):
    return frappe.get_doc("Supplier", supplier_name).tax_id


def generate_date_chunks(start_year):
    today = datetime.now()
    chunk_start = datetime(start_year, 1, 1)
    chunks = []

    while chunk_start <= today:
        chunk_end = chunk_start + timedelta(days=89)
        if chunk_end > today:
            chunk_end = today
        chunks.append((
            chunk_start.strftime("%d/%m/%Y"),
            chunk_end.strftime("%d/%m/%Y"),
        ))
        chunk_start = chunk_end + timedelta(days=1)

    return chunks


def get_suppliers_by_tax_id(tax_id):
    return frappe.get_all("Supplier", filters={"tax_id": tax_id}, pluck="name")


@frappe.whitelist()
def sync_all_by_year(year, tax_id=None):
    try:
        chunks = generate_date_chunks(int(year))

        if tax_id:
            suppliers = get_suppliers_by_tax_id(tax_id)
        else:
            suppliers = frappe.get_all("Supplier", pluck="name")

        chunks_failed = 0
        errors = []

        for nvfac_fini, nvfac_ffin in chunks:
            try:
                for supplier_id in suppliers:
                    sync_by_supplier(
                        nvfac_esta="E",
                        supplier_id=supplier_id,
                        get_tax_id_fn=get_supplier_tax_id,
                        send_request_fn=send_request_status,
                        create_log_fn=create_sync_log,
                        create_lines_fn=create_sync_lines,
                        commit_fn=lambda: frappe.db.commit(),
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
            except Exception as chunk_error:
                frappe.db.rollback()
                frappe.log_error(
                    frappe.get_traceback(),
                    "sync_all_by_year chunk {} - {}".format(nvfac_fini, nvfac_ffin),
                )
                chunks_failed += 1
                errors.append(
                    "Chunk {} - {} failed: {}".format(
                        nvfac_fini, nvfac_ffin, str(chunk_error)
                    )
                )

        return {
            "success": True,
            "suppliers_count": len(suppliers),
            "chunks_total": len(chunks),
            "chunks_failed": chunks_failed,
            "errors": errors,
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "sync_all_by_year")
        return {"success": False, "error": "Internal error"}