"""
order_transform.py (GP)
========================
Transformacion API GP -> tuplas DB para ordenes de compra.
Extraido de uses_cases/sales_order/sync_by_supplier.py (get_doc_base, set_item)
y services/sync_doc.py (set_doc, set_doc_list, set_error).
Mantiene el mapeo de campos y el comportamiento original.
"""

import json

from qp_supplier_front.exception.sync import (
    ExceptionSyncProductNotFound,
    ExceptionSyncRequestNotList,
)
from qp_supplier_front.infrastructure.strategies.gp.order_validate import (
    assert_amount_max_length_valid,
)


def build_order_tuple(order, doc_id, now, company):
    return (
        doc_id,
        order.get("orderId"),
        order.get("docDate"),
        order.get("vendor"),
        order.get("prmDate"),
        order.get("docDate"),
        now,
        company,
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_order_item_tuple(item, doc_id, items_valid, now, request_list_key_id):
    item_id = "{}:{}".format(doc_id, item.get(request_list_key_id))
    return (
        item_id,
        item.get(request_list_key_id),
        item.get("qtyOrder"),
        1,
        item.get("unitCost"),
        item.get("unitCost"),
        item.get("extdCost"),
        doc_id,
        "items",
        "Purchase Order",
        item.get("extdCost"),
        items_valid.get("item_name", ""),
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_error_tuple(error, errors, doc_id, item_code, doctype, key, now):
    error_id = "{}:{}:{}".format(doc_id, item_code, key)
    errors[error_id] = (
        error_id,
        error.get("line"),
        error.get("code"),
        error.get("error"),
        doc_id,
        "lines_errors",
        doctype,
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_order_records(orders_data, items_valid, now, company, strategy):
    """
    Construye las tuplas de docs, items y errores para las ordenes nuevas.
    Retorna (docs, items, errors, doc_errors) donde doc_errors es una lista
    de dicts {title, message} para loguear errores a nivel de documento.
    """
    docs = {}
    items = {}
    errors = {}
    doc_errors = []

    request_key_id = strategy["request_key_id"]
    request_list_key = strategy["request_list_key"]
    request_list_key_id = strategy["request_list_key_id"]
    doctype = strategy["doctype"]

    for doc_new in orders_data:
        doc_id = _build_doc_id(doc_new, request_key_id)

        try:
            docs[doc_id] = build_order_tuple(doc_new, doc_id, now, company)
            _build_order_items(
                doc_new,
                doc_id,
                items_valid,
                items,
                errors,
                request_list_key,
                request_list_key_id,
                doctype,
                now,
            )
        except ExceptionSyncRequestNotList as e:
            doc_errors.append({
                "title": str(e),
                "message": json.dumps(doc_new),
            })
        except Exception as e:
            doc_errors.append({
                "title": str(e),
                "message": json.dumps(doc_new),
            })

    return docs, items, errors, doc_errors


def _build_doc_id(doc_new, request_key_id):
    return "{}:{}".format(doc_new.get(request_key_id), doc_new.get("vendor"))


def _build_order_items(
    doc_new,
    doc_id,
    items_valid,
    items,
    errors,
    request_list_key,
    request_list_key_id,
    doctype,
    now,
):
    products = doc_new.get(request_list_key)

    if not products:
        raise ExceptionSyncRequestNotList(doc_new.get("orderId"))

    count = 0

    for key, item in enumerate(products):
        count += 1

        try:
            item_code = item.get(request_list_key_id)

            if item_code not in items_valid:
                raise ExceptionSyncProductNotFound(item_code)

            assert_amount_max_length_valid(item.get("extdCost"), item_code, doc_id)

            item_id = "{}:{}".format(doc_id, item_code)
            items[item_id] = build_order_item_tuple(
                item, doc_id, items_valid, now, request_list_key_id
            )

        except ExceptionSyncProductNotFound as e:
            error = {
                "line": count,
                "code": item.get(request_list_key_id),
                "error": str(e),
            }
            build_error_tuple(
                error, errors, doc_id, item.get(request_list_key_id), doctype, key, now
            )

        except Exception as e:
            error = {
                "line": 0,
                "code": 0,
                "error": str(e),
            }
            build_error_tuple(
                error, errors, doc_id, item.get(request_list_key_id), doctype, key, now
            )
