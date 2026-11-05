"""
sync_supplier.py
==================
Orquestador de sincronizacion de proveedores.
Itera sobre los flujos configurados (GP, BC) e inyecta las
implementaciones reales (API fetch, log, throw) al nucleo puro.
"""

import frappe
from qp_supplier_front.services.flow_config import is_flow_configured
from qp_supplier_front.infrastructure.strategies.registry import get_supplier_strategy
from qp_supplier_front.infrastructure.adapters.fetch_adapter import fetch_supplier as gp_fetch
from qp_supplier_front.uses_cases.supplier.sync_core import sync_supplier_to_flow
from qp_supplier_front.services.utils import add_log


FETCH_MAP = {
    "GP": gp_fetch,
}


def sync_supplier_to_flows(supplier):
    """
    Sincroniza un proveedor a todos los flujos externos configurados.

    Retorna lista de dicts con resultado por flujo.
    """
    results = []

    for flow in ("GP", "BC"):
        if not is_flow_configured(flow, "supplier"):
            continue

        strategy = get_supplier_strategy(flow)
        fetch_fn = FETCH_MAP.get(flow, gp_fetch)

        result = sync_supplier_to_flow(
            supplier=supplier,
            flow=flow,
            strategy=strategy,
            fetch_fn=fetch_fn,
            log_fn=add_log,
            throw_fn=frappe.throw,
            log_error_fn=frappe.log_error,
        )

        results.append(result)

    return results
