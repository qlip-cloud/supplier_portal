"""
sync_core.py (payment_receipt)
================================
Nucleo puro de sincronizacion de recibos de pago.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(API, DB, commit, log) son inyectadas como callbacks.

Soporta items hijos (GP) y sin items (BC).
Incluye sync_payments_window para sincronizar por ventanas de fechas
sin depender del endpoint global sin filtros.
"""

import time

from qp_supplier_front.exception.sync import (
    ExceptionSyncResponseEmpty,
    ExceptionSyncNoNewRecords,
)
from qp_supplier_front.infrastructure.strategies.registry import get_payment_strategy


def sync_payments(
    supplier_id,
    flow,
    fetch_fn,
    last_creation_fn,
    existing_ids_fn,
    commit_fn,
    now,
):
    strategy = get_payment_strategy(flow)

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

    payments_data = result.get(strategy["request_key"], [])

    _validate_payments(payments_data, strategy["request_key"])

    candidate_ids = _extract_ids(payments_data, strategy["request_key_id"])

    existing_ids = existing_ids_fn(
        strategy["doctype"],
        strategy["db_fields"]["id_field"],
        candidate_ids,
    )

    new_payments = _filter_new(
        payments_data,
        existing_ids,
        strategy["request_key_id"],
    )

    if not new_payments:
        raise ExceptionSyncNoNewRecords(strategy["doctype"])

    docs, items = strategy["transform"](
        new_payments,
        strategy["name"],
        now,
    )

    strategy["persist"]["insert_payments"](docs, now)

    if items:
        strategy["persist"]["insert_items"](items, now)

    commit_fn()

    return len(docs)


def sync_all_payments(
    flow,
    fetch_fn,
    existing_ids_fn,
    commit_fn,
    now,
):
    strategy = get_payment_strategy(flow)

    result = fetch_fn(strategy["endpoints"]["all"])

    _validate_response(result, strategy["request_key"])

    payments_data = result.get(strategy["request_key"], [])

    _validate_payments(payments_data, strategy["request_key"])

    candidate_ids = _extract_ids(payments_data, strategy["request_key_id"])

    existing_ids = existing_ids_fn(
        strategy["doctype"],
        strategy["db_fields"]["id_field"],
        candidate_ids,
    )

    new_payments = _filter_new(
        payments_data,
        existing_ids,
        strategy["request_key_id"],
    )

    if not new_payments:
        raise ExceptionSyncNoNewRecords(strategy["doctype"])

    docs, items = strategy["transform"](
        new_payments,
        strategy["name"],
        now,
    )

    strategy["persist"]["insert_payments"](docs, now)

    if items:
        strategy["persist"]["insert_items"](items, now)

    commit_fn()

    return len(docs)


def sync_payments_window(
    supplier_id,
    flow,
    window_start,
    window_end,
    fetch_fn,
    existing_ids_fn,
    commit_fn,
    log_sync_fn,
    now,
    scope="supplier",
):
    strategy = get_payment_strategy(flow)
    started_at = time.time()

    _safe_log(
        log_sync_fn,
        "In Progress",
        window_start,
        window_end,
    )
    commit_fn()

    if scope == "global":
        param = strategy["build_all_range_param"](
            str(window_start), str(window_end)[:10]
        )
        endpoint = strategy["endpoints"]["all_range"]
    else:
        param = strategy["build_param"](
            supplier_id,
            last_date=str(window_start),
            now=str(window_end)[:10],
        )
        endpoint = strategy["endpoints"]["per_supplier_range"]

    result = fetch_fn(endpoint, param=param)

    if strategy["request_key"] not in result:
        raise ExceptionSyncResponseEmpty(strategy["request_key"])

    payments_data = result.get(strategy["request_key"]) or []

    if not payments_data:
        _safe_log(
            log_sync_fn,
            "NoNewRecords",
            window_start,
            window_end,
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

    candidate_ids = _extract_ids(payments_data, strategy["request_key_id"])

    existing_ids = existing_ids_fn(
        strategy["doctype"],
        strategy["db_fields"]["id_field"],
        candidate_ids,
    )

    new_payments = _filter_new(
        payments_data,
        existing_ids,
        strategy["request_key_id"],
    )

    if not new_payments:
        _safe_log(
            log_sync_fn,
            "NoNewRecords",
            window_start,
            window_end,
            records_found=len(payments_data),
            records_inserted=0,
            records_skipped=len(payments_data),
            duration_ms=_elapsed(started_at),
        )
        commit_fn()
        return {
            "status": "NoNewRecords",
            "found": len(payments_data),
            "inserted": 0,
            "skipped": len(payments_data),
        }

    docs, items = strategy["transform"](
        new_payments,
        strategy["name"],
        now,
    )

    strategy["persist"]["insert_payments"](docs, now)

    if items:
        strategy["persist"]["insert_items"](items, now)

    _safe_log(
        log_sync_fn,
        "Success",
        window_start,
        window_end,
        records_found=len(payments_data),
        records_inserted=len(docs),
        records_skipped=len(payments_data) - len(new_payments),
        duration_ms=_elapsed(started_at),
    )
    commit_fn()

    return {
        "status": "Success",
        "found": len(payments_data),
        "inserted": len(docs),
        "skipped": len(payments_data) - len(new_payments),
    }


def _safe_log(log_sync_fn, status, window_start, window_end, **kwargs):
    try:
        log_sync_fn(
            status=status,
            window_start=window_start,
            window_end=window_end,
            **kwargs
        )
    except Exception:
        pass


def _elapsed(started_at):
    return int((time.time() - started_at) * 1000)


def _extract_ids(payments_data, id_field):
    return {pymt.get(id_field) for pymt in payments_data if pymt.get(id_field)}


def _validate_response(result, request_key):
    if request_key not in result or not result[request_key]:
        raise ExceptionSyncResponseEmpty(request_key)


def _validate_payments(payments, request_key):
    if not payments:
        raise ExceptionSyncNoNewRecords(request_key)


def _filter_new(payments_data, existing_ids, id_field):
    return [
        pymt for pymt in payments_data
        if pymt.get(id_field) not in existing_ids
    ]
