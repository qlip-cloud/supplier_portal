"""
supplier_strategy.py (BC)
==========================
Estrategia de sincronizacion de proveedores para BC (placeholder).
Cuando se implemente el servicio BC para proveedores, completar
build_bc_supplier_payload, is_bc_found y validate_bc_response.
"""


def build_bc_supplier_payload(supplier):
    return None


def is_bc_found(response):
    return False


def validate_bc_response(response, supplier_name, log_error_fn, throw_fn):
    pass


BC_SUPPLIER_STRATEGY = {
    "name": "BC",
    "endpoints": {
        "find": "supplier_find",
        "insert": "supplier_insert",
        "update": "supplier_update",
    },
    "build_payload": build_bc_supplier_payload,
    "is_found": is_bc_found,
    "validate_response": validate_bc_response,
}
