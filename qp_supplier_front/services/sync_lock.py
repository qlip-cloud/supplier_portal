"""
sync_lock.py
==============
Lock de exclusion mutua por dominio de sincronizacion basado en Redis
(SET NX EX via frappe.cache), con dueño y heartbeat.

Motivacion: un lock eventual (crash del worker, reinicio del servidor)
quedaba tomado hasta 6h sin que nadie supiera quién lo puso. Ahora cada
lock es un LEASE:

- TTL corto por defecto (5 min) renovado por heartbeat durante el sync.
- Guarda {owner, token, started_at, updated_at, expires_at} en el valor.
- acquire roba (stale-steal) si el lock no tiene TTL, ya venció o el valor
  no es legible (formato viejo), para que un sync fallido se desbloquee solo.
- release es por token: solo libera el lock que este proceso tomo.
- force_release / release_if_stale para desbloqueo manual o de colgados.

Describe quién bloqueó, cuándo empezó y hasta cuándo es válido el lease.
"""

import json
import os
import socket
import time
import uuid

LOCK_PREFIX = "qp_supplier_front:sync_lock"
DEFAULT_TTL = 5 * 60
WAIT_INTERVAL = 10


def frappe_cache():
    import frappe
    return frappe.cache()


def _key(domain):
    return frappe_cache().make_key("{}:{}".format(LOCK_PREFIX, domain))


def _default_owner():
    try:
        host = socket.gethostname()
    except Exception:
        host = "unknown"
    return "{}:{}".format(host, os.getpid())


def _now():
    return int(time.time() * 1000)


def _payload(token, owner, ttl):
    now_ms = _now()
    return {
        "token": token,
        "owner": owner,
        "started_at": now_ms,
        "updated_at": now_ms,
        "expires_at": now_ms + (ttl * 1000),
    }


def _decode(raw):
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _is_expired(payload):
    return _now() > (payload.get("expires_at") or 0)


def _delete(key):
    try:
        frappe_cache().delete(key)
    except Exception:
        pass


def acquire(domain, ttl=DEFAULT_TTL, owner=None):
    """Adquiere el lock. Retorna payload (dict con token) o None si esta tomado.
    Fail-open: si Redis falla, retorna un payload (permite que el sync corra)."""
    token = uuid.uuid4().hex
    owner = owner or _default_owner()

    try:
        c = frappe_cache()
        key = _key(domain)

        try:
            raw = c.get(key)
        except Exception:
            raw = None

        if raw:
            payload = _decode(raw)
            try:
                ttl_left = c.ttl(key)
            except Exception:
                ttl_left = -1
            no_ttl = ttl_left is not None and ttl_left == -1
            if no_ttl or payload is None or _is_expired(payload):
                # colgado: sin TTL, valor ilegible (formato viejo) o lease vencido
                _delete(key)
            else:
                return None

        set_ok = c.set(
            key,
            json.dumps(_payload(token, owner, ttl)),
            nx=True,
            ex=ttl,
        )

        if set_ok:
            return _payload(token, owner, ttl)
        return None
    except Exception:
        # fail-open: si redis falla, permitir que la sincronizacion corra
        return _payload(token, owner, ttl)


def heartbeat(domain, token, ttl=DEFAULT_TTL):
    """Renueva el lease. Solo si el token actual coincide (no reanima uno ajeno)."""
    try:
        c = frappe_cache()
        key = _key(domain)
        raw = c.get(key)
        payload = _decode(raw)
        if not payload or payload.get("token") != token:
            return False
        payload["updated_at"] = _now()
        payload["expires_at"] = _now() + (ttl * 1000)
        c.set(key, json.dumps(payload), xx=True, ex=ttl)
        return True
    except Exception:
        return False


def release(domain, token=None):
    """Libera el lock. Con token, solo si es el mismo (no libera el de otro)."""
    try:
        c = frappe_cache()
        key = _key(domain)
        if token is not None:
            raw = c.get(key)
            payload = _decode(raw)
            if not payload or payload.get("token") != token:
                return
        c.delete(key)
    except Exception:
        pass


def force_release(domain):
    """Desbloqueo manual incondicional."""
    _delete(_key(domain))


def release_if_stale(domain):
    """Borra el lock solo si no tiene TTL, no es legible o ya vencio."""
    try:
        c = frappe_cache()
        key = _key(domain)
        raw = c.get(key)
        if not raw:
            return
        payload = _decode(raw)
        try:
            ttl_left = c.ttl(key)
        except Exception:
            ttl_left = -1
        no_ttl = ttl_left is not None and ttl_left == -1
        if no_ttl or payload is None or _is_expired(payload):
            _delete(key)
    except Exception:
        pass


def is_locked(domain):
    try:
        c = frappe_cache()
        key = _key(domain)

        try:
            raw = c.get(key)
        except Exception:
            raw = None

        if raw is None:
            try:
                return bool(c.exists(key))
            except Exception:
                return False

        payload = _decode(raw)
        return payload is not None and not _is_expired(payload)
    except Exception:
        return False


def wait_for(domain, timeout=300):
    """
    Espera hasta obtener el lock (para jobs full manuales que deben correr).
    Retorna True si lo obtuvo, False si expiro el timeout. Al retornar True
    el lock quedó adquirido por esta llamada a acquire().
    """
    waited = 0

    while True:
        if acquire(domain):
            return True
        if waited >= timeout:
            return False
        time.sleep(WAIT_INTERVAL)
        waited += WAIT_INTERVAL