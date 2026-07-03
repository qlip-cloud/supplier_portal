from qp_supplier_front.constant.endpoint import DOCUMENT_DETAIL_DOCUMENT
from qp_supplier_front.services.document_sync import (
    build_detail_params,
    is_successful_response,
    get_response_description,
)


def sync_detail(
    get_uncompleted_lines_fn,
    send_request_fn,
    create_document_detail_fn,
    log_sync_attempt_fn,
    mark_line_completed_fn,
    commit_fn,
):
    lines = get_uncompleted_lines_fn()

    for line in lines:
        nvpro_ndoc = line.get("nvpro_ndoc")
        nvfac_esta = line.get("nvfac_esta")
        nvfac_nume = line.get("nvfac_nume")

        param = build_detail_params(nvpro_ndoc, nvfac_esta, nvfac_nume)

        response, status = send_request_fn(
            endpoint_code=DOCUMENT_DETAIL_DOCUMENT,
            param=param,
            is_query_param=True,
        )

        if is_successful_response(response, status):
            document_data = response.get("Document", {})
            attached_list = response.get("lAttached", [])

            create_document_detail_fn(
                line["name"], document_data, attached_list
            )

            log_sync_attempt_fn(
                line["name"], "Success", None, response
            )

            mark_line_completed_fn(line["name"])

        else:
            error_msg = get_response_description(response) or str(response)
            log_sync_attempt_fn(
                line["name"], "Error", error_msg, response
            )

    commit_fn()
