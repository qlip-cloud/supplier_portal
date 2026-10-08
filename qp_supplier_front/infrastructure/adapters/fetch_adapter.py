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

    `send_request` devuelve {} ante un fallo HTTP (p. ej. 404) sin lanzar
    excepcion, por lo que el sync lo interpretaba como "sin registros". Aqui
    se valida el status y, ante cualquier error, se registra en el Error Log
    y se re-lanza para que la ventana quede marcada como Error.
    """
    import frappe

    try:
        response, status = send_request_status(endpoint, param=param)
        assert_payment_receipts_ok(endpoint, response, status)
        return response
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Error en peticion de recibos GP: {}".format(endpoint),
        )
        raise


def assert_payment_receipts_ok(endpoint, response, status):
    if status != 200:
        raise Exception(
            "Peticion de recibos GP {} fallo con HTTP {}".format(endpoint, status)
        )
    if isinstance(response, dict) and response.get("status") not in (None, 200):
        raise Exception(
            "Peticion de recibos GP {} devolvio status {}".format(
                endpoint, response.get("status")
            )
        )


def fetch_supplier(endpoint, **kwargs):
    return send_request(endpoint, **kwargs)

