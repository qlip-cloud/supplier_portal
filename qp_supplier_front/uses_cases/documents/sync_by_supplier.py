from datetime import datetime, timedelta
from qp_supplier_front.constant.endpoint import DOCUMENT_LIST_DOCUMENTS
from qp_supplier_front.services.document_sync import (
    build_document_params,
    is_successful_response,
)


def get_yesterday_date_str():
    return (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")


def get_day_before_yesterday_date_str():
    return (datetime.now() - timedelta(days=2)).strftime("%d/%m/%Y")


def get_today_date_str():
    return datetime.now().strftime("%d/%m/%Y")


def get_default_nvfac_esta():
    return "T"


def get_default_nvfac_fini():
    return get_day_before_yesterday_date_str()


def get_default_nvfac_ffin():
    return get_today_date_str()


def sync_by_supplier(
    supplier_id,
    get_tax_id_fn,
    send_request_fn,
    create_log_fn,
    create_lines_fn,
    commit_fn,
    nvfac_esta=None,
    nvfac_fini=None,
    nvfac_ffin=None,
):
    tax_id = get_tax_id_fn(supplier_id)

    nvfac_esta = nvfac_esta if nvfac_esta is not None else get_default_nvfac_esta()
    nvfac_fini = nvfac_fini if nvfac_fini is not None else get_default_nvfac_fini()
    nvfac_ffin = nvfac_ffin if nvfac_ffin is not None else get_default_nvfac_ffin()

    param = build_document_params(tax_id, nvfac_esta, nvfac_fini, nvfac_ffin)

    response, status = send_request_fn(
        endpoint_code=DOCUMENT_LIST_DOCUMENTS,
        param=param,
        is_query_param=True,
    )

    log_name = create_log_fn(
        supplier_id, tax_id, DOCUMENT_LIST_DOCUMENTS, param, response, status
    )

    if is_successful_response(response, status):
        create_lines_fn(log_name, response.get("LDocuments", []))

    commit_fn()

    return log_name
