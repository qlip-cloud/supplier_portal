"""
registry.py
=============
Registro central de estrategias de sincronizacion.

Cada estrategia (GP, BC, futuro) se registra aqui.
El resolver recibe un nombre de estrategia y retorna su configuracion.

Las estrategias se importan de forma perezosa dentro de los resolvers
para permitir importar este modulo sin Frappe instalado (lazy imports).
"""

STRATEGY_KEYS = ("GP", "BC")


def _load_strategy(strategy_name):
    if strategy_name == "GP":
        from qp_supplier_front.infrastructure.strategies.gp.strategy import (
            GP_STRATEGY,
        )
        return GP_STRATEGY
    from qp_supplier_front.infrastructure.strategies.bc.strategy import (
        BC_STRATEGY,
    )
    return BC_STRATEGY


def _load_payment_strategy(strategy_name):
    if strategy_name == "GP":
        from qp_supplier_front.infrastructure.strategies.gp.receipt_strategy import (
            GP_RECEIPT_STRATEGY,
        )
        return GP_RECEIPT_STRATEGY
    from qp_supplier_front.infrastructure.strategies.bc.receipt_strategy import (
        BC_RECEIPT_STRATEGY,
    )
    return BC_RECEIPT_STRATEGY


def _load_supplier_strategy(strategy_name):
    if strategy_name == "GP":
        from qp_supplier_front.infrastructure.strategies.gp.supplier_strategy import (
            GP_SUPPLIER_STRATEGY,
        )
        return GP_SUPPLIER_STRATEGY
    from qp_supplier_front.infrastructure.strategies.bc.supplier_strategy import (
        BC_SUPPLIER_STRATEGY,
    )
    return BC_SUPPLIER_STRATEGY


def get_strategy(strategy_name):
    if strategy_name not in STRATEGY_KEYS:
        raise ValueError(
            "Estrategia desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(STRATEGY_KEYS))
            )
        )
    return _load_strategy(strategy_name)


def get_payment_strategy(strategy_name):
    if strategy_name not in STRATEGY_KEYS:
        raise ValueError(
            "Estrategia de pago desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(STRATEGY_KEYS))
            )
        )
    return _load_payment_strategy(strategy_name)


def get_supplier_strategy(strategy_name):
    if strategy_name not in STRATEGY_KEYS:
        raise ValueError(
            "Estrategia de proveedor desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(STRATEGY_KEYS))
            )
        )
    return _load_supplier_strategy(strategy_name)
