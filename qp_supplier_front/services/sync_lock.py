"""
sync_lock.py
==============
Lock de exclusion mutua por dominio de sincronizacion (ordenes/recibos)
basado en Redis (SET NX EX via frappe.cache).

Evita que la sincronizacion programada (cron 5 min) se ejecute mientras
una sincronizacion manual esta corriendo, y viceversa.

- acquire: atomico, retorna True si obtuvo el lock, False si ya estaba tomado.
- release: libera el lock.
- wait_for: espera (polling) hasta obtener el lock o agotar el timeout.
- El TTL evita que un job caido deje el lock tomado para siempre.
"""

LOCK_PREFIX = "qp_supplier_front:sync_lock"
DEFAULT_TTL = 6 * 60 * 60
WAIT_INTERVAL = 10


def _key(domain):
    return frappe_cache().make_key("{}:{}".format(LOCK_PREFIX, domain))


def frappe_cache():
    import frappe
    return frappe.cache()


def acquire(domain, ttl=DEFAULT_TTL):
    """Intenta adquirir el lock. Retorna True si lo obtuvo."""
    try:
        return bool(frappe_cache().set(_key(domain), "1", nx=True, ex=ttl))
    except Exception:
        # fail-open: si redis falla, permitir que la sincronizacion corra
        return True


def release(domain):
    try:
        frappe_cache().delete(_key(domain))
    except Exception:
        pass


def is_locked(domain):
    try:
        return bool(frappe_cache().exists(_key(domain)))
    except Exception:
        return False


def wait_for(domain, timeout=300):
    """
    Espera hasta obtener el lock (para jobs full manuales que deben correr).
    Retorna True si lo obtuvo, False si expiro el timeout.
    """
    import time

    waited = 0

    while True:
        if acquire(domain):
            return True
        if waited >= timeout:
            return False
        time.sleep(WAIT_INTERVAL)
        waited += WAIT_INTERVAL
