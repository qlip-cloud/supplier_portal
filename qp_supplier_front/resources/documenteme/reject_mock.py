import frappe
from frappe import parse_json
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._reject_base import run_reject
from qp_supplier_front.resources.documenteme import simulation


@frappe.whitelist()
def reject_test(doc_names, motive, is_invoice_error, fail_all=None):
    try:
        fail_all_flag = bool(parse_json(fail_all)) if fail_all else False
        send_fn = simulation.build_http_double(
            fail_all=fail_all_flag,
            already_applied_once=True,
        )
        run_reject(doc_names, motive, is_invoice_error, send_fn)

    except Exception as error:
        response(500, "Error al rechazar (test): {}".format(str(error)))