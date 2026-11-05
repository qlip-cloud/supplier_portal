# -*- coding: utf-8 -*-
"""
session.py (documenteme simulation)
====================================
Estado de la sesion de simulacion: el MemoryStore activo para el modo
simulador. Durante un request con el flag activo, el sync simulado y las
lecturas de la vista comparten el mismo store en memoria; nada se escribe en
la base de datos real.

Es infraestructura (estado de sesion), no logica de negocio.
"""

from qp_supplier_front.simulation.store import MemoryStore

_STORE = None


def store():
    """Retorna el MemoryStore activo de la sesion (creado lazy)."""
    global _STORE
    if _STORE is None:
        _STORE = MemoryStore()
    return _STORE


def reset():
    """Descarta el store actual (nueva sesion de simulacion)."""
    global _STORE
    _STORE = None