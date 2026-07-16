"""
sync_core.py
==============
Nucleo puro de sincronizacion de facturas de compra.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(API, DB, commit, log) son inyectadas como callbacks.

Sigue el patron de documents/sync_by_supplier.py (Clean Architecture / DI).
"""

from qp_supplier_front.exception.sync import (
    ExceptionSyncResponseEmpty,
    ExceptionSyncNoNewRecords,
)
from qp_supplier_front.infrastructure.strategies.registry import get_strategy


def sync_invoices(
    supplier_id,
    flow,
    fetch_fn,
    last_creation_fn,
    existing_ids_fn,
    commit_fn,
    now,
):
    strategy = get_strategy(flow)

    last_date = last_creation_fn(
        strategy["doctype"],
        supplier_id,
        strategy["db_fields"]["order_field"],
    )

    last_date_for_param = str(last_date) if last_date else None
    param = strategy["build_param"](supplier_id, last_date=last_date_for_param, now=now[:10])

    if last_date:
        endpoint = strategy["endpoints"]["per_supplier_range"]
    else:
        endpoint = strategy["endpoints"]["per_supplier"]

    result = fetch_fn(endpoint, param=param)

    _validate_response(result, strategy["request_key"])

    invoices_data = result.get(strategy["request_key"], [])

    _validate_invoices(invoices_data, strategy["request_key"])

    candidate_ids = _extract_ids(invoices_data, strategy["request_key_id"])

    existing_ids = existing_ids_fn(
        strategy["doctype"],
        strategy["db_fields"]["id_field"],
        candidate_ids,
    )

    new_invoices = _filter_new(
        invoices_data,
        existing_ids,
        strategy["request_key_id"],
    )

    if not new_invoices:
        raise ExceptionSyncNoNewRecords(strategy["doctype"])

    docs = strategy["transform"](
        new_invoices,
        strategy["name"],
        now,
    )

    strategy["persist"]["insert_invoices"](docs, now)

    commit_fn()

    return len(docs)


def sync_all_invoices(
    flow,
    fetch_fn,
    existing_ids_fn,
    commit_fn,
    now,
):
    strategy = get_strategy(flow)

    result = fetch_fn(strategy["endpoints"]["all"])

    _validate_response(result, strategy["request_key"])

    invoices_data = result.get(strategy["request_key"], [])

    _validate_invoices(invoices_data, strategy["request_key"])

    candidate_ids = _extract_ids(invoices_data, strategy["request_key_id"])

    existing_ids = existing_ids_fn(
        strategy["doctype"],
        strategy["db_fields"]["id_field"],
        candidate_ids,
    )

    new_invoices = _filter_new(
        invoices_data,
        existing_ids,
        strategy["request_key_id"],
    )

    if not new_invoices:
        raise ExceptionSyncNoNewRecords(strategy["doctype"])

    docs = strategy["transform"](
        new_invoices,
        strategy["name"],
        now,
    )

    strategy["persist"]["insert_invoices"](docs, now)

    commit_fn()

    return len(docs)


def sync_all_suppliers_invoices(
    flow,
    fetch_fn,
    get_suppliers_fn,
    last_creation_fn,
    existing_ids_fn,
    commit_fn,
    log_error_fn,
    now,
):
    supplier_ids = get_suppliers_fn()
    synced_count = 0
    errors = []

    for supplier_id in supplier_ids:
        try:
            count = sync_invoices(
                supplier_id=supplier_id,
                flow=flow,
                fetch_fn=fetch_fn,
                last_creation_fn=last_creation_fn,
                existing_ids_fn=existing_ids_fn,
                commit_fn=commit_fn,
                now=now,
            )
            synced_count += count
        except ExceptionSyncNoNewRecords:
            continue
        except ExceptionSyncResponseEmpty:
            continue
        except Exception as e:
            log_error_fn(
                message="Supplier {}: {}".format(supplier_id, str(e)),
                title="Error sync supplier invoices ({})".format(flow),
            )
            errors.append({
                "supplier_id": supplier_id,
                "error": str(e),
            })

    return {
        "synced_count": synced_count,
        "errors": errors,
    }


def _extract_ids(invoices_data, id_field):
    return {inv.get(id_field) for inv in invoices_data if inv.get(id_field)}


def _validate_response(result, request_key):
    if request_key not in result or not result[request_key]:
        raise ExceptionSyncResponseEmpty(request_key)


def _validate_invoices(invoices, request_key):
    if not invoices:
        raise ExceptionSyncNoNewRecords(request_key)


def _filter_new(invoices_data, existing_ids, id_field):
    return [
        inv for inv in invoices_data
        if inv.get(id_field) not in existing_ids
    ]

