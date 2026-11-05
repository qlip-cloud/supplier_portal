# -*- coding: utf-8 -*-
"""
auto_approve_confirmation.py (documenteme) -- infraestructura
=============================================================
Notificacion asincronica de APROBACION a documenteme (030 -> 032 -> 033).

Replica el patron de auto_reject.py pero para la secuencia de aprobacion
cuyo evento final es 033:

  1. El servicio update_document recibe la confirmacion de BC
     (invoice_id + confirmation_id), guarda el confirmation_id, marca el
     documento en estado "PA" (En proceso de Aprobacion) y programa el
     primer evento.
  2. Los eventos 030 -> 032 -> 033 se envian UNO POR JOB
     (event_job.run_documenteme_event); el dispatcher (event_dispatch)
     materializa los siguientes a partir de qp_event_next_at.
  3. Si la secuencia completa tiene exito, el documento se marca "A"
     (Aprobado) con nvfac_ueve "033" y se resuelven sus alertas.
  4. Si se agotan los intentos, se inserta una alerta y el documento
     permanece en "PA" (En proceso de Aprobacion).
"""

import frappe

from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    _is_error,
    _build_payload,
)
from qp_supplier_front.uses_cases.documenteme.reject_retry import (
    is_already_applied,
)

APPROVE_JOB_METHOD = (
    "qp_supplier_front.resources.documenteme.auto_approve_confirmation.approve_confirmation_batch_job"
)

APPROVAL_EVENT_ORDER = ["030", "032", "033"]

APPROVAL_EVENT_CONFIG = {
    "030": {"nvint_desc": "Factura aprobada"},
    "032": {"nvint_desc": "Factura aprobada"},
    "033": {"nvfac_esta": "A", "nvint_desc": "Factura aprobada"},
}


def get_approval_config(master_setup=None):
    """Reutiliza la configuracion de reintentos del setup global."""
    if master_setup is not None:
        source = master_setup
    else:
        from qp_supplier_front.infrastructure.adapters.master_setup_source import (
            RealMasterSetupSource,
        )
        source = RealMasterSetupSource(frappe_module=frappe)
    return source.reject_config()


def enqueue_approve_confirmation(doc_name):
    """Programa la notificacion de aprobacion (un evento por job).

    Marca la secuencia "A" (030 -> 032 -> 033) en el documento y encola el
    primer evento; el dispatcher (event_dispatch) materializa los siguientes.
    """
    from qp_supplier_front.resources.documenteme.event_job import (
        initialize_event_schedule_db,
        schedule_event,
    )

    initialize_event_schedule_db(doc_name, "A")
    schedule_event(doc_name)


# =========================================================================
# Reanudacion de la secuencia de aprobacion
# =========================================================================
def get_approval_resume_index(event_logs):
    """Indice de APPROVAL_EVENT_ORDER desde donde reanudar el envio.

    Ante cualquier fallo se reinicia la secuencia completa desde el 030.
    Misma idea que get_reject_resume_index pero para la secuencia de
    aprobacion (033). El parametro se conserva para mantener la firma,
    pero siempre se devuelve 0.
    """
    return 0


def build_approval_events(doc, company_tax_id, resume_index, base_state=None):
    """Eventos de aprobacion pendientes desde resume_index hasta el final."""
    events = []
    for idx, event_code in enumerate(APPROVAL_EVENT_ORDER):
        if idx < resume_index:
            continue
        events.append({
            "event_code": event_code,
            "payload": _build_payload(
                doc, event_code, APPROVAL_EVENT_CONFIG, company_tax_id,
                base_state=base_state,
            ),
        })
    return events


def is_sequence_successful(sent):
    """True si el ultimo evento enviado es el 033 sin error (aprobacion ok).

    Un 033 que responde "ya aplicado" tambien se considera aprobado.
    """
    last = sent[-1] if sent else None
    if not last or last["event_code"] != "033":
        return False
    return (not _is_error(last["response"], last["status"])
            or is_already_applied(last["response"]))


# =========================================================================
# Job de aprobacion: programacion de eventos (un evento por job)
# =========================================================================
def approve_confirmation_batch_job(doc_names, http_fn=None):
    """Compatibilidad: programa UN evento por factura (sin sleeps).

    El envio de la secuencia 030/032/033 ahora lo materializa
    event_job/event_dispatch. Se conserva el nombre para callers/tests.
    """
    from qp_supplier_front.resources.documenteme.event_job import (
        schedule_event,
    )

    results = []
    for doc_name in (doc_names or []):
        results.append((doc_name, schedule_event(doc_name, http_fn=http_fn)))
    return results


def make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
