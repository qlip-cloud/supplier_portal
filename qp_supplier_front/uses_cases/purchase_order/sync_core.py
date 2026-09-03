"""
sync_core.py (purchase_order)
==============================
Nucleo puro de sincronizacion de ordenes de compra por ventanas de fechas.
No tiene imports a Frappe. Todas las dependencias (API, DB, commit, log)
son inyectadas como callbacks.

Cada llamada procesa una ventana [window_start, window_end] para un
proveedor usando el endpoint por proveedor con rango de fechas
(ORDER_SUPPLIER_DATE_RANGE), evitando el endpoint global sin filtros.
"""

import time

from qp_supplier_front.exception.sync import (
    ExceptionSyncResponseEmpty,
)


def sync_orders_window(
    supplier_id,
    window_start,
    window_end,
    now,
    strategy,
    fetch_fn,
    existing_ids_fn,
    get_items_fn,
    get_company_fn,
    commit_fn,
    log_sync_fn,
    log_error_fn,
):
    started_at = time.time()

    _log_window(
        log_sync_fn,
        status="In Progress",
        window_start=window_start,
        window_end=window_end,
    )
    commit_fn()

    param = strategy["build_param"](supplier_id, window_start, window_end)
    endpoint = strategy["endpoints"]["per_supplier_range"]

    result = fetch_fn(endpoint, param=param)

    if strategy["request_key"] not in result:
        raise ExceptionSyncResponseEmpty(strategy["request_key"])

    orders_data = result[strategy["request_key"]] or []

    if not orders_data:
        _log_window(
            log_sync_fn,
            status="NoNewRecords",
            window_start=window_start,
            window_end=window_end,
            records_found=0,
            records_inserted=0,
            records_skipped=0,
            duration_ms=_elapsed(started_at),
        )
        commit_fn()
        return {
            "status": "NoNewRecords",
            "found": 0,
            "inserted": 0,
            "skipped": 0,
        }

    candidate_ids = _extract_ids(orders_data, strategy["request_key_id"])
    existing_ids = existing_ids_fn(
        strategy["doctype"],
        strategy["db_fields"]["id_field"],
        candidate_ids,
    )
    new_orders = _filter_new(orders_data, existing_ids, strategy["request_key_id"])

    if not new_orders:
        _log_window(
            log_sync_fn,
            status="NoNewRecords",
            window_start=window_start,
            window_end=window_end,
            records_found=len(orders_data),
            records_inserted=0,
            records_skipped=len(orders_data),
            duration_ms=_elapsed(started_at),
        )
        commit_fn()
        return {
            "status": "NoNewRecords",
            "found": len(orders_data),
            "inserted": 0,
            "skipped": len(orders_data),
        }

    items_valid = get_items_fn()
    company = get_company_fn()

    docs, items, errors, doc_errors = strategy["transform"](
        new_orders, items_valid, now, company, strategy
    )

    strategy["persist"]["insert_orders"](docs, now)
    strategy["persist"]["insert_items"](items, now)
    strategy["persist"]["insert_errors"](errors, now)

    for doc_error in doc_errors:
        _safe(log_error_fn, doc_error.get("message"), doc_error.get("title"))

    _log_window(
        log_sync_fn,
        status="Success",
        window_start=window_start,
        window_end=window_end,
        records_found=len(orders_data),
        records_inserted=len(docs),
        records_skipped=len(orders_data) - len(new_orders),
        duration_ms=_elapsed(started_at),
    )
    commit_fn()

    return {
        "status": "Success",
        "found": len(orders_data),
        "inserted": len(docs),
        "skipped": len(orders_data) - len(new_orders),
    }


def _extract_ids(orders_data, id_field):
    return {order.get(id_field) for order in orders_data if order.get(id_field)}


def _filter_new(orders_data, existing_ids, id_field):
    return [
        order for order in orders_data
        if order.get(id_field) not in existing_ids
    ]


def _log_window(log_sync_fn, **kwargs):
    _safe(log_sync_fn, **kwargs)


def _safe(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception:
        pass


def _elapsed(started_at):
    return int((time.time() - started_at) * 1000)
