"""
registry.py
=============
Registro central de estrategias de sincronizacion.

Cada estrategia (GP, BC, futuro) se registra aqui.
El resolver recibe un nombre de estrategia y retorna su configuracion.
"""

from qp_supplier_front.infrastructure.strategies.gp.strategy import GP_STRATEGY
from qp_supplier_front.infrastructure.strategies.bc.strategy import BC_STRATEGY
from qp_supplier_front.infrastructure.strategies.gp.receipt_strategy import GP_RECEIPT_STRATEGY
from qp_supplier_front.infrastructure.strategies.bc.receipt_strategy import BC_RECEIPT_STRATEGY
from qp_supplier_front.infrastructure.strategies.gp.supplier_strategy import GP_SUPPLIER_STRATEGY
from qp_supplier_front.infrastructure.strategies.bc.supplier_strategy import BC_SUPPLIER_STRATEGY


STRATEGIES = {
    "GP": GP_STRATEGY,
    "BC": BC_STRATEGY,
}

PAYMENT_STRATEGIES = {
    "GP": GP_RECEIPT_STRATEGY,
    "BC": BC_RECEIPT_STRATEGY,
}

SUPPLIER_STRATEGIES = {
    "GP": GP_SUPPLIER_STRATEGY,
    "BC": BC_SUPPLIER_STRATEGY,
}


def get_strategy(strategy_name):
    if strategy_name not in STRATEGIES:
        raise ValueError(
            "Estrategia desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(STRATEGIES.keys()))
            )
        )
    return STRATEGIES[strategy_name]


def get_payment_strategy(strategy_name):
    if strategy_name not in PAYMENT_STRATEGIES:
        raise ValueError(
            "Estrategia de pago desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(PAYMENT_STRATEGIES.keys()))
            )
        )
    return PAYMENT_STRATEGIES[strategy_name]


def get_supplier_strategy(strategy_name):
    if strategy_name not in SUPPLIER_STRATEGIES:
        raise ValueError(
            "Estrategia de proveedor desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(SUPPLIER_STRATEGIES.keys()))
            )
        )
    return SUPPLIER_STRATEGIES[strategy_name]

