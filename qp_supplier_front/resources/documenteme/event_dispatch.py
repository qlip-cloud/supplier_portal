# -*- coding: utf-8 -*-
"""
event_dispatch.py (documenteme) -- infraestructura
==================================================
Dispatcher del reintento de eventos documenteme (cron cada minuto).

NO envia HTTP ni duerme: solo consulta los documentos vencidos (una consulta
indexada) y encola UN job de un evento por cada uno. El worker se libera tras
cada peticion; la espera entre eventos vive en `qp_event_next_at` (BD), no en
un `time.sleep`.

Tope por tick (`DUE_LIMIT`): si el backlog supera el tope, el resto sigue
"vencido" (qp_event_next_at en el pasado) y lo reclama el tick siguiente,
ordenando por fecha ascendente para que no haya inanicion. Nunca se descarta.

Idempotencia: antes de encolar, el dispatcher toma el lock por documento y lo
pasa al job; asi dos ticks (o manual + auto) no encolan el mismo documento.
"""

from datetime import datetime

import frappe

from qp_supplier_front.resources.documenteme.event_job import (
    EVENT_JOB_METHOD,
    event_lock_domain,
)
from qp_supplier_front.services import sync_lock

DUE_LIMIT = 150
DISPATCH_LOCK_TTL = 300
PENDING_STATES = ("PR", "PA")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_due_events(limit=DUE_LIMIT):
    """Nombres de documentos con un evento vencido (mas viejos primero).

    Consulta sargable apoyada en el indice (nvfac_esta, qp_event_next_at):
    range scan por estado+fecha, sin funciones sobre columnas. La primera
    query cubre los vencidos; la segunda, por robustez, los que aun no
    tienen `qp_event_next_at` (los legados se backfillean en migrate).
    """
    states = list(PENDING_STATES)
    limit = int(limit)
    due_rows = frappe.db.sql(
        """
        SELECT name
        FROM `tabqp_SP_DocumentDetail`
        WHERE nvfac_esta IN %(states)s
          AND qp_reject_retry_enabled = 1
          AND qp_event_next_at <= %(now)s
        ORDER BY qp_event_next_at ASC
        LIMIT %(limit)s
        """,
        {"states": states, "now": _now_str(), "limit": limit},
        as_dict=True,
    )
    names = [row.get("name") for row in (due_rows or [])]

    if len(names) < limit:
        null_rows = frappe.db.sql(
            """
            SELECT name
            FROM `tabqp_SP_DocumentDetail`
            WHERE nvfac_esta IN %(states)s
              AND qp_reject_retry_enabled = 1
              AND qp_event_next_at IS NULL
            ORDER BY modified ASC
            LIMIT %(limit)s
            """,
            {"states": states, "limit": limit},
            as_dict=True,
        )
        for row in (null_rows or []):
            if len(names) >= limit:
                break
            name = row.get("name")
            if name and name not in names:
                names.append(name)

    return names


def dispatch_pending_events(limit=DUE_LIMIT):
    """Encola un job de un evento por cada documento vencido."""
    if _is_simulation_enabled():
        return []

    dispatched = []
    for name in get_due_events(limit=limit):
        token = sync_lock.acquire(event_lock_domain(name), ttl=DISPATCH_LOCK_TTL)
        if token is None:
            continue
        try:
            frappe.enqueue(
                EVENT_JOB_METHOD,
                doc_name=name,
                lock_token=token.get("token"),
                queue="long",
                timeout=600,
                job_name="documenteme event {}".format(name),
            )
            dispatched.append(name)
        except Exception:
            sync_lock.release(event_lock_domain(name), token.get("token"))
            frappe.log_error(
                frappe.get_traceback(),
                "documenteme event dispatch - {}".format(name),
            )
    return dispatched


def _is_simulation_enabled():
    from qp_supplier_front.resources.documenteme import runtime
    try:
        return runtime.is_simulation_enabled()
    except Exception:
        return False
