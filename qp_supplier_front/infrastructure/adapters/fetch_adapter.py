"""
fetch_adapter.py
=================
Adaptador para obtener datos desde la API externa (GP middleware).
Implementa el contrato de fetch para las estrategias de sync.
"""

from qp_authorization.use_case.bearer.authorize import (
    send_request,
    send_request_status,
)


def fetch_invoices(endpoint, param=None):
    return send_request(endpoint, param=param)


def fetch_payment_receipts(endpoint, param=None):
    """Peticion de recibos GP.

    El endpoint GetPaymentDate devuelve HTTP 404 cuando el rango de fechas no
    tiene recibos para el proveedor (no es un error real: es una ventana
    vacia). Por eso 404 se traduce a respuesta vacia (NoNewRecords) en vez de
    lanzar excepcion. Otros estados (5xx, body status != 200) si se registran
    en el Error Log y se re-lanzan para marcar la ventana como Error.
    """
    import frappe

    try:
        response, status = send_request_status(endpoint, param=param)
        return assert_gp_range_ok(endpoint, response, status)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Error en peticion de recibos GP: {}".format(endpoint),
        )
        raise


def fetch_purchase_invoices(endpoint, param=None):
    """Peticion de facturas GP (mismo contrato que fetch_payment_receipts).

    El endpoint GetInvoiceDateC tambien devuelve HTTP 404 para rangos sin
    facturas; 404 se traduce a ventana vacia, los errores reales se registran
    en el Error Log y se re-lanzan.
    """
    import frappe

    try:
        response, status = send_request_status(endpoint, param=param)
        return assert_gp_range_ok(endpoint, response, status)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Error en peticion de facturas GP: {}".format(endpoint),
        )
        raise


def assert_gp_range_ok(endpoint, response, status):
    if status == 404:
        return {}
    if status != 200:
        raise Exception(
            "Peticion GP {} fallo con HTTP {}".format(endpoint, status)
        )
    if isinstance(response, dict) and response.get("status") not in (None, 200):
        raise Exception(
            "Peticion GP {} devolvio status {}".format(
                endpoint, response.get("status")
            )
        )
    return response


def fetch_supplier(endpoint, **kwargs):
    return send_request(endpoint, **kwargs)

