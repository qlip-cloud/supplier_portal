"""
sync_core.py
==============
Nucleo puro de sincronizacion de facturas de compra.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(API, DB, commit, log) son inyectadas como callbacks.

Sigue el patron de documents/sync_by_supplier.py (Clean Architecture / DI).
Incluye sync_invoices_window para sincronizar por ventanas de fechas
sin depender del endpoint global sin filtros.
"""

import time

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
    log_skipped_fn=None,
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

    new_invoices, skipped = strategy["filter"](new_invoices)

    if log_skipped_fn:
        for skip in skipped:
            log_skipped_fn(skip)

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
    log_skipped_fn=None,
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

    new_invoices, skipped = strategy["filter"](new_invoices)

    if log_skipped_fn:
        for skip in skipped:
            log_skipped_fn(skip)

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
    log_skipped_fn=None,
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
                log_skipped_fn=log_skipped_fn,
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


def sync_invoices_window(
    supplier_id,
    flow,
    window_start,
    window_end,
    fetch_fn,
    existing_ids_fn,
    commit_fn,
    log_sync_fn,
    now,
    log_skipped_fn=None,
    scope="supplier",
):
    strategy = get_strategy(flow)
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

    invoices_data = result.get(strategy["request_key"]) or []

    if not invoices_data:
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

    new_invoices, skipped = strategy["filter"](new_invoices)

    if log_skipped_fn:
        for skip in skipped:
            _safe(log_skipped_fn, skip)

    if not new_invoices:
        _safe_log(
            log_sync_fn,
            "NoNewRecords",
            window_start,
            window_end,
            records_found=len(invoices_data),
            records_inserted=0,
            records_skipped=len(invoices_data),
            duration_ms=_elapsed(started_at),
        )
        commit_fn()
        return {
            "status": "NoNewRecords",
            "found": len(invoices_data),
            "inserted": 0,
            "skipped": len(invoices_data),
        }

    docs = strategy["transform"](
        new_invoices,
        strategy["name"],
        now,
    )

    strategy["persist"]["insert_invoices"](docs, now)

    _safe_log(
        log_sync_fn,
        "Success",
        window_start,
        window_end,
        records_found=len(invoices_data),
        records_inserted=len(docs),
        records_skipped=len(invoices_data) - len(new_invoices),
        duration_ms=_elapsed(started_at),
    )
    commit_fn()

    return {
        "status": "Success",
        "found": len(invoices_data),
        "inserted": len(docs),
        "skipped": len(invoices_data) - len(new_invoices),
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


def _safe(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception:
        pass


def _elapsed(started_at):
    return int((time.time() - started_at) * 1000)


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

