import frappe
from qp_authorization.use_case.basic.authorize import send_request_status
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._reject_base import run_reject


@frappe.whitelist()
def reject(doc_names, motive, is_invoice_error):
    try:
        run_reject(doc_names, motive, is_invoice_error, send_request_status)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al rechazar: {}".format(str(error)))