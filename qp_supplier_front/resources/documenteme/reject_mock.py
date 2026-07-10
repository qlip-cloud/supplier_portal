import frappe
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._reject_base import run_reject


_COUNTERS = {}


def _build_test_sequence():
    def send_request_status_test(endpoint_code=None, payload=None):
        event_code = payload.get("Nveve_dian") if payload else None
        key = event_code or "unknown"
        _COUNTERS[key] = _COUNTERS.get(key, 0) + 1
        attempt = _COUNTERS[key]

        if attempt == 1:
            return (
                {
                    "Result": 1,
                    "Description": "El evento {} ya fue emitido".format(event_code),
                },
                200,
            )

        return (
            {
                "Result": 0,
                "Description": "Estado de documento actualizado.",
                "Document": None,
                "lAttached": None,
            },
            200,
        )

    return send_request_status_test


@frappe.whitelist()
def reject_test(doc_names, motive, is_invoice_error):
    try:
        send_fn = _build_test_sequence()
        run_reject(doc_names, motive, is_invoice_error, send_fn)

    except Exception as error:
        response(500, "Error al rechazar (test): {}".format(str(error)))