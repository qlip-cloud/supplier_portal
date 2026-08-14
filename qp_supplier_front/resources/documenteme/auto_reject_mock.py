import frappe
from frappe import parse_json
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme.auto_reject import run_auto_reject

_COUNTERS = {}


def _build_test_http(fail_cont_numbers=None, fail_all=False):
    """http_fn mockeado para el rechazo automatico.

    - fail_cont_numbers: lista de Nvfac_cont (numero de consecutivo de la
      factura) que siempre fallan (secuencia se corta -> queda en E).
    - fail_all: todas las facturas fallan.
    """
    fail_set = set(fail_cont_numbers or [])

    def http_fn(payload, url, headers, method):
        cont = payload.get("Nvfac_cont") if payload else None
        if fail_all or (fail_set and cont in fail_set):
            return (
                {
                    "Result": 1,
                    "Description": "Error simulado en el evento",
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
def auto_reject_test(fail_cont_numbers=None, fail_all=None):
    try:
        fails = parse_json(fail_cont_numbers) if fail_cont_numbers else None
        fail_all_flag = bool(parse_json(fail_all)) if fail_all else False
        http_fn = _build_test_http(fail_cont_numbers=fails, fail_all=fail_all_flag)
        result = run_auto_reject(http_fn=http_fn)
        frappe.db.commit()
        response(200, "Rechazo automatico (test) ejecutado", result)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al rechazar automaticamente (test): {}".format(str(error)))
