# -*- coding: utf-8 -*-
"""
auto_approve_state.py
=====================
Estado transitorio (cache) de las facturas que estan en un job de
auto-aprobacion documenteme.

Mientras el job esta encolado o corriendo, la lista muestra "Procesando..."
en lugar de "Lista para Registro", para que el usuario no crea que tiene que
aprobarla manualmente. Es solo una marca de UI: no cambia `nvfac_esta` ni
interviene en el flujo de aprobacion.

Se lee con `expires=True` para que `get_value` no guarde un `None` en la
cache local del proceso cuando la marca todavia no existe (si lo hiciera, el
`None` taparia el valor escrito por el endpoint en la misma sesion).
"""

PROCESSING_PREFIX = "documenteme_auto_approve_doc:"
PROCESSING_TTL = 3600


def _cache():
    import frappe
    return frappe.cache()


def mark_processing(doc_names, ttl=PROCESSING_TTL):
    """Marca las facturas que quedaron dentro de un job de auto-aprobacion."""
    try:
        cache = _cache()
    except Exception:
        return
    for doc_name in (doc_names or []):
        if not doc_name:
            continue
        try:
            cache.set_value(
                PROCESSING_PREFIX + str(doc_name), 1, expires_in_sec=ttl)
        except Exception:
            pass


def clear_processing(doc_names):
    """Quita la marca cuando el job termino (o la factura salio del job)."""
    names = [
        PROCESSING_PREFIX + str(doc_name)
        for doc_name in (doc_names or [])
        if doc_name
    ]
    if not names:
        return
    try:
        _cache().delete_value(names)
    except Exception:
        pass


def is_processing(doc_name):
    """True si la factura esta dentro de un job de auto-aprobacion."""
    if not doc_name:
        return False
    try:
        return bool(_cache().get_value(
            PROCESSING_PREFIX + str(doc_name), expires=True))
    except Exception:
        return False
