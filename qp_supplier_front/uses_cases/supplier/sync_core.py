"""
sync_core.py
==============
Nucleo de sincronizacion de proveedores por flujo (GP, BC).
No tiene imports a Frappe. Las dependencias de infraestructura
(API, log, throw) son inyectadas como callbacks.
"""


def sync_supplier_to_flow(supplier, flow, strategy, fetch_fn, log_fn, throw_fn, log_error_fn):
    """
    Sincroniza un proveedor a un flujo externo (GP, BC).

    Retorna dict con resultado de la operacion.
    """
    payload = strategy["build_payload"](supplier)

    if payload is None:
        return {
            "flow": flow,
            "synced": False,
            "skipped": True,
            "reason": "not_implemented",
        }

    find_result = fetch_fn(strategy["endpoints"]["find"], param=supplier.tax_id)

    exists = strategy["is_found"](find_result)

    endpoint = strategy["endpoints"]["update"] if exists else strategy["endpoints"]["insert"]

    result = fetch_fn(endpoint, payload=payload)

    log_fn("Create/Update Supplier ({})".format(flow), payload, result, supplier.name)

    strategy["validate_response"](result, supplier.name, log_error_fn, throw_fn)

    return {
        "flow": flow,
        "synced": True,
        "skipped": False,
        "action": "update" if exists else "insert",
    }
