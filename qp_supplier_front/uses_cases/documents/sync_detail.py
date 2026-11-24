from qp_supplier_front.constant.endpoint import DOCUMENT_DETAIL_DOCUMENT
from qp_supplier_front.services.document_sync import (
    build_detail_params,
    is_successful_response,
    get_response_description,
)


def _log(log_fn, message):
    if not log_fn:
        return
    try:
        log_fn(message)
    except Exception:
        pass


def sync_detail(
    get_uncompleted_lines_fn,
    send_request_fn,
    create_document_detail_fn,
    log_sync_attempt_fn,
    mark_line_completed_fn,
    commit_fn,
    get_company_tax_id_fn=None,
    heartbeat_fn=None,
    log_fn=None,
):
    lines = get_uncompleted_lines_fn()
    total = len(lines)

    _log(log_fn, "sync_detail: inicio, {} factura(s) pendiente(s)".format(total))

    created_names = []

    for position, line in enumerate(lines, start=1):
        if heartbeat_fn:
            heartbeat_fn()
        nvpro_ndoc = line.get("nvpro_ndoc")
        nvfac_esta = line.get("nvfac_esta")
        nvfac_nume = line.get("nvfac_nume")

        _log(
            log_fn,
            "sync_detail: procesando {}/{} factura={} proveedor={}".format(
                position, total, nvfac_nume, nvpro_ndoc
            ),
        )

        nvemp_nnit = nvpro_ndoc
        if get_company_tax_id_fn:
            tax_id = get_company_tax_id_fn(line.get("document_sync_log"))
            if tax_id:
                nvemp_nnit = tax_id

        param = build_detail_params(nvemp_nnit, nvpro_ndoc, nvfac_esta, nvfac_nume)

        response, status = send_request_fn(
            endpoint_code=DOCUMENT_DETAIL_DOCUMENT,
            param=param,
            is_query_param=True,
        )

        if is_successful_response(response, status):
            document_data = response.get("Document", {})
            attached_list = response.get("lAttached", [])

            doc = create_document_detail_fn(
                line["name"], document_data, attached_list
            )
            if doc and doc.name:
                created_names.append(doc.name)

            log_sync_attempt_fn(
                line["name"], "Success", None, response
            )

            mark_line_completed_fn(line["name"])

            _log(
                log_fn,
                "sync_detail: OK {}/{} factura={}".format(
                    position, total, nvfac_nume
                ),
            )

        else:
            error_msg = get_response_description(response) or str(response)
            log_sync_attempt_fn(
                line["name"], "Error", error_msg, response
            )

            _log(
                log_fn,
                "sync_detail: ERROR {}/{} factura={} -> {}".format(
                    position, total, nvfac_nume, error_msg
                ),
            )

    commit_fn()

    _log(
        log_fn,
        "sync_detail: fin, {} creada(s) de {}".format(len(created_names), total),
    )

    return created_names
