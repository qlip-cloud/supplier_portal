import frappe
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme.auto_reject import run_auto_reject

_COUNTERS = {}


def _build_test_http():
    def http_fn(payload, url, headers, method):
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

    return http_fn


@frappe.whitelist()
def auto_reject_test():
    try:
        http_fn = _build_test_http()
        result = run_auto_reject(http_fn=http_fn)
        frappe.db.commit()
        response(200, "Rechazo automatico (test) ejecutado", result)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al rechazar automaticamente (test): {}".format(str(error)))
