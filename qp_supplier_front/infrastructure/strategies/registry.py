"""
registry.py
=============
Registro central de estrategias de sincronizacion.

Cada estrategia (GP, BC, futuro) se registra aqui.
El resolver recibe un nombre de estrategia y retorna su configuracion.
"""

from qp_supplier_front.infrastructure.strategies.gp.strategy import GP_STRATEGY
from qp_supplier_front.infrastructure.strategies.bc.strategy import BC_STRATEGY


STRATEGIES = {
    "GP": GP_STRATEGY,
    "BC": BC_STRATEGY,
}


def get_strategy(strategy_name):
    if strategy_name not in STRATEGIES:
        raise ValueError(
            "Estrategia desconocida: {}. Opciones: {}".format(
                strategy_name, ", ".join(sorted(STRATEGIES.keys()))
            )
        )
    return STRATEGIES[strategy_name]

