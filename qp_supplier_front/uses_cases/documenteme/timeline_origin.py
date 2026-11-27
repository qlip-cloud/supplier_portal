# -*- coding: utf-8 -*-
"""
timeline_origin.py (uses_cases - documenteme)
=============================================
Origen de las entradas del historial de facturas documenteme.

El historial debe distinguir si una aprobacion, rechazo o asignacion la hizo
una persona (manual) o el sistema (automatico). La distincion NO se puede
deducir de `frappe.session.user`: `frappe.enqueue` propaga el usuario que
disparo el job y el worker hace `frappe.set_user(user)`, por lo que un job
automatico lanzado desde el boton "Actualizar" de un usuario corre como ese
usuario y quedaria registrado a su nombre.

Por eso los flujos automaticos abren un contexto `timeline_origin(AUTOMATIC)`
y los manuales dejan el origen por defecto (manual). El adaptador del timeline
usa ese origen para decidir el autor de la fila: el nombre real en manual y
`Sistema` en automatico.

Python 3.6 compatible: threading.local + contextmanager. Cada worker/hilo de
Frappe atiende una peticion/job a la vez, por lo que el estado por hilo es
suficiente.
"""

from contextlib import contextmanager
from functools import wraps
import threading

ORIGIN_MANUAL = "manual"
ORIGIN_AUTOMATIC = "automatic"

SYSTEM_LABEL = "Sistema"

_state = threading.local()


def current_origin():
    """Origen vigente del hilo actual (manual si nadie lo fijo)."""
    return getattr(_state, "origin", None) or ORIGIN_MANUAL


def set_origin(origin):
    """Fija el origen vigente y devuelve el anterior (para restaurarlo)."""
    previous = getattr(_state, "origin", None)
    _state.origin = origin or ORIGIN_MANUAL
    return previous


def reset_origin(previous):
    """Restaura el origen previo devuelto por `set_origin`."""
    _state.origin = previous


def is_automatic(origin=None):
    """True si el origen indicado (o el vigente) es automatico."""
    return (origin or current_origin()) == ORIGIN_AUTOMATIC


def actor_label(user, origin=None):
    """Autor visible en el historial para el origen indicado.

    Automatico -> "Sistema" (no el usuario que disparo el job).
    Manual -> el nombre del usuario que ejecuto la accion.
    """
    if is_automatic(origin):
        return SYSTEM_LABEL
    return user or ""


@contextmanager
def timeline_origin(origin):
    """Context manager que fija el origen durante el bloque."""
    previous = set_origin(origin)
    try:
        yield
    finally:
        reset_origin(previous)


def automatic_timeline(fn):
    """Decorador: ejecuta la funcion con origen automatico.

    Se aplica a los puntos de entrada de los flujos automaticos (aprobacion,
    rechazo, asignacion, promocion a V, confirmacion externa) para que el
    historial registre "Sistema" aunque el job haya corrido con el usuario que
    disparo el "Actualizar".
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with timeline_origin(ORIGIN_AUTOMATIC):
            return fn(*args, **kwargs)

    return wrapper


@contextmanager
def system_user():
    """Ejecuta el bloque como Administrator SOLO en un worker de fondo.

    Los jobs encolados con `frappe.enqueue` corren con el usuario que los
    disparo (`execute_job` hace `frappe.set_user(user)`). Para que las
    facturas y el historial de un proceso automatico queden como del sistema,
    el job cambia a Administrator y restaura el usuario previo al terminar.

    Nunca cambia el usuario dentro de una peticion web viva: `set_user`
    reinicia `frappe.local.form_dict/cache/session` y afectaria el resto de
    la peticion. En ese caso el bloque corre con el usuario actual y el
    historial igual queda marcado como automatico por `timeline_origin`.

    No otorga permisos al usuario humano: el cambio es thread-local y vive
    solo en el proceso que ejecuta el job; la sesion/cookie del navegador
    no se toca.
    """
    try:
        import frappe
        local_request = getattr(getattr(frappe, "local", None), "request", None)
    except Exception:
        yield
        return

    if local_request is not None:
        yield
        return

    previous = getattr(frappe.session, "user", None) or "Administrator"
    frappe.set_user("Administrator")
    try:
        yield
    finally:
        frappe.set_user(previous)


def system_job(fn):
    """Decorador: corre el job de fondo como Administrator (ver system_user)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with system_user():
            return fn(*args, **kwargs)

    return wrapper
