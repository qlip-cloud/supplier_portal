"""
log_adapter.py
================
Adaptador de registro de sincronizacion.
Crea y actualiza registros en qp_SP_SyncLog para dar trazabilidad de cada
ventana sincronizada (ordenes, recibos y facturas) en los modos full e
incremental.

El nucleo puro recibe el callback log_sync_fn (DI); la implementacion
real de Frappe se inyecta desde el wrapper @frappe.whitelist().
"""


def log_sync(
    sync_type,
    supplier,
    flow,
    sync_mode,
    window_start,
    window_end,
    status,
    records_found=None,
    records_inserted=None,
    records_skipped=None,
    duration_ms=None,
    error_message=None,
    sync_date=None,
):
    import frappe

    log = frappe.new_doc("qp_SP_SyncLog")
    log.sync_type = sync_type
    log.supplier = supplier
    log.flow = flow
    log.sync_mode = sync_mode
    log.sync_date = sync_date
    log.window_start = window_start
    log.window_end = window_end
    log.status = status
    log.records_found = records_found
    log.records_inserted = records_inserted
    log.records_skipped = records_skipped
    log.duration_ms = duration_ms
    log.error_message = error_message
    log.insert()
    return log.name


def update_sync_log(name, **fields):
    import frappe

    fields = {key: value for key, value in fields.items() if value is not None}

    if fields:
        frappe.db.set_value("qp_SP_SyncLog", name, fields)

    return name


def build_sync_log_fn(
    sync_type,
    supplier,
    flow,
    sync_mode,
    sync_date,
    track_in_progress=True,
):
    """
    Factory que devuelve un closure de log con ciclo de vida create -> update
    sobre una sola fila de qp_SP_SyncLog por ventana.

    - Con track_in_progress=True (full): la primera llamada con status
      "In Progress" crea la fila; las siguientes la actualizan.
    - Con track_in_progress=False (incremental): la llamada "In Progress"
      es no-op y la fila se crea recien con el status final (una sola fila
      por ventana, sin ruido).
    """
    state = {"name": None}

    def log(
        status,
        window_start,
        window_end,
        records_found=None,
        records_inserted=None,
        records_skipped=None,
        duration_ms=None,
        error_message=None,
    ):
        if status == "In Progress" and not track_in_progress:
            return None

        if state["name"] is None:
            state["name"] = log_sync(
                sync_type=sync_type,
                supplier=supplier,
                flow=flow,
                sync_mode=sync_mode,
                window_start=window_start,
                window_end=window_end,
                status=status,
                records_found=records_found,
                records_inserted=records_inserted,
                records_skipped=records_skipped,
                duration_ms=duration_ms,
                error_message=error_message,
                sync_date=sync_date,
            )
        else:
            update_sync_log(
                state["name"],
                status=status,
                records_found=records_found,
                records_inserted=records_inserted,
                records_skipped=records_skipped,
                duration_ms=duration_ms,
                error_message=error_message,
            )

        return state["name"]

    return log
