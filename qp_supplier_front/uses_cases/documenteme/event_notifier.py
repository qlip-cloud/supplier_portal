import json
from qp_supplier_front.constant.endpoint import DOCUMENTEME_EVENT_DOCUMENT

EVENT_ORDER = ["030", "032", "031"]

# Estados validos de documenteme por evento. Documenteme solo reconoce
# E (Registrado), A (Aprobado), R (Rechazado), V. Los estados internos
# (BCC, PA, PR) nunca deben salir en los payloads de notificacion.
DOCUMENTEME_EVENT_STATES = {
    "030": "E",
    "032": "E",
    "031": "R",
    "033": "A",
}


def _get_last_event_idx(logs):
    last_idx = -1
    for log in (logs or []):
        if log.get("status") in (200, 201) and log.get("event_code") in EVENT_ORDER:
            idx = EVENT_ORDER.index(log.get("event_code"))
            if idx > last_idx:
                last_idx = idx
    return last_idx


def _get_nvfac_esta(doc, event_code, event_config, base_state=None):
    if event_code in DOCUMENTEME_EVENT_STATES:
        return DOCUMENTEME_EVENT_STATES[event_code]
    override = event_config.get(event_code, {})
    if override.get("nvfac_esta"):
        return override.get("nvfac_esta")
    return base_state if base_state is not None else doc.nvfac_esta


def _build_payload(doc, event_code, event_config, company_tax_id, base_state=None):
    return {
        "Nvemp_nnit": company_tax_id,
        "Nvpro_ndoc": doc.nvpro_ndoc,
        "Nvfac_cont": doc.nvfac_cont,
        "Nvfac_esta": _get_nvfac_esta(doc, event_code, event_config, base_state),
        "Nveve_dian": event_code,
        "Nvint_desc": event_config.get(event_code, {}).get(
            "nvint_desc", "Rechazo por error de factura"
        ),
    }


def _get_error_message(response):
    if not isinstance(response, dict):
        return str(response)
    return (
        response.get("Description")
        or response.get("Message")
        or response.get("message")
        or response.get("error")
        or response.get("Error")
        or str(response)
    )


def _is_error(response, status):
    if status not in (200, 201):
        return True
    if isinstance(response, dict) and response.get("Result") == 1:
        return True
    return False


def _append_log(doc, event_code, payload, response, status, now_fn):
    log_row = doc.append("event_logs")
    log_row.event_code = event_code
    log_row.payload = json.dumps(payload)
    log_row.response = json.dumps(response) if not isinstance(response, str) else response
    log_row.status = status
    log_row.error_message = _get_error_message(response) if _is_error(response, status) else ""
    log_row.attempt_date = now_fn()


def send_event_sequence(doc, event_config, send_request_fn, commit_fn,
                        get_company_tax_id_fn, now_fn, required_nvfac_esta=None):
    if required_nvfac_esta is not None and doc.nvfac_esta != required_nvfac_esta:
        raise Exception(
            "El documento debe tener estado '{}' para procesar. Estado actual: {}".format(
                required_nvfac_esta, doc.nvfac_esta
            )
        )

    company_tax_id = get_company_tax_id_fn()
    last_idx = _get_last_event_idx(doc.get("event_logs"))

    for idx, event_code in enumerate(EVENT_ORDER):
        if idx <= last_idx:
            continue

        payload = _build_payload(doc, event_code, event_config, company_tax_id)

        try:
            response, status = send_request_fn(
                endpoint_code=DOCUMENTEME_EVENT_DOCUMENT,
                payload=payload,
            )
        except Exception as e:
            response = str(e)
            status = 500

        _append_log(doc, event_code, payload, response, status, now_fn)

        doc.save()
        commit_fn()

        if _is_error(response, status):
            raise Exception(
                "Error en notificacion paso {}: {}".format(
                    event_code, _get_error_message(response)
                )
            )