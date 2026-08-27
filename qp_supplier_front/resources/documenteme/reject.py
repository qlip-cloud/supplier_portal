import frappe
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._reject_base import run_reject


@frappe.whitelist()
def reject(doc_names, motive, is_invoice_error):
    try:
        # run_reject es asincrono (marca PR y encola el job de fondo); el
        # parametro send_request_fn es ignorado por el flujo actual, por lo
        # que no se construye ningun double aqui (la logica de simulacion de
        # eventos vive en auto_reject.reject_batch_job).
        run_reject(doc_names, motive, is_invoice_error, None)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al rechazar: {}".format(str(error)))