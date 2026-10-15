import frappe
from frappe import parse_json
from datetime import datetime
from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_company_tax_id as _adapter_get_company_tax_id,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.services.documenteme_access import (
    can_see_all_documenteme,
    get_assigned_sync_line_names,
)
from qp_supplier_front.services.role_resolver import get_active_role
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice

ALLOWED_ROLES = {"Administrador Documenteme", "Administrador Sede Documenteme"}

# Estados desde los que se permite un rechazo manual. Coinciden con los
# estados de analisis de la aprobacion (E/V/T): una factura ya creada en BC,
# en proceso o final (BCC/PA/PR/A/R/SR) no debe retroceder a "PR".
REJECTABLE_STATES = ("E", "V", "T")


def _get_company_tax_id():
    """NIT de la compania del usuario actual (delega en el adapter)."""
    return _adapter_get_company_tax_id(frappe_module=frappe)


def _has_permission(user_roles):
    active = get_active_role(user_roles)
    return active in ALLOWED_ROLES


def _make_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _unique(values):
    """Elimina duplicados conservando el orden (evita encolar dos veces)."""
    seen = set()
    result = []
    for value in (values or []):
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_doc_names(raw):
    """Normaliza el parametro doc_names a una lista de nombres unicos.

    Acepta una lista JSON o un unico nombre. Un JSON invalido, vacio o None
    devuelve lista vacia (el llamador responde 400).
    """
    try:
        value = parse_json(raw)
    except Exception:
        return []
    if isinstance(value, (list, tuple)):
        names = [str(name) for name in value if name]
    elif isinstance(value, str) and value:
        names = [value]
    else:
        names = []
    return _unique(names)


def _release_claimed_receipts(doc):
    """Libera las recepciones reclamadas por la factura al rechazarla.

    Una factura rechazada no debe retener recibos (quedarian huerfanos e
    invisibles para otras facturas de la misma OC). release_receipts solo
    afecta recibos cuyo qp_invoice coincide con la factura.
    """
    from qp_supplier_front.infrastructure.adapters.receipt_claim_adapter import (
        claimed_receipt_names,
        release_receipts,
    )

    names = claimed_receipt_names(doc.nvfac_nume, frappe_module=frappe)
    if names:
        release_receipts(doc, names, frappe_module=frappe)


def run_reject(doc_names_raw, motive, is_invoice_error_raw, send_request_fn):
    """Rechazo manual ASINCRONO.

    Marca cada factura como "PR" (En proceso de rechazo) persistiendo el
    motivo y el indicador de error, y encola el job de fondo que envia la
    secuencia 030 -> 032 -> 031 con reintentos hacia documenteme. No
    bloquea el servicio ni depende de la velocidad del servidor externo.
    """
    from qp_supplier_front.resources.documenteme.event_job import (
        initialize_event_schedule,
        schedule_event,
    )

    doc_names = _normalize_doc_names(doc_names_raw)
    is_invoice_error = parse_json(is_invoice_error_raw)
    if is_invoice_error is None:
        # Sin indicador explicito se asume "error de factura" (notifica): es
        # el comportamiento seguro; solo un false explicito omite eventos.
        is_invoice_error = True

    user_roles = frappe.get_roles()
    if not _has_permission(user_roles):
        response(403, "No tiene permisos para rechazar facturas")
        return

    if not doc_names:
        response(400, "Debe seleccionar al menos una factura")
        return

    motive = str(motive or "").strip()
    if not motive:
        response(400, "El motivo del rechazo es obligatorio")
        return

    see_all = can_see_all_documenteme(user_roles)
    assigned_lines = (
        None if see_all
        else set(get_assigned_sync_line_names(frappe.session.user))
    )

    docs = []
    blocked = []
    forbidden = []
    for doc_name in doc_names:
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        if not see_all and doc.get("document_sync_line") not in assigned_lines:
            forbidden.append(doc_name)
            continue
        if doc.nvfac_esta not in REJECTABLE_STATES:
            blocked.append({"doc": doc_name, "state": doc.nvfac_esta})
            continue
        docs.append(doc)

    if forbidden:
        response(
            403,
            "No tiene permisos para rechazar algunas facturas",
            {"forbidden": forbidden},
        )
        return

    if blocked:
        response(
            400,
            "Algunas facturas no se pueden rechazar en su estado actual",
            {"blocked": blocked},
        )
        return

    rejects = []
    direct_rejected = []
    for doc in docs:
        if is_cash_invoice(doc.nvfac_conv) or not is_invoice_error:
            # Contado, o rechazo sin error de factura: se marca "R" directo
            # sin notificar eventos a documenteme (qp_is_event_completed deja
            # constancia de que no hay evento DIAN en cola).
            doc.nvfac_esta = "R"
            doc.qp_is_event_completed = 1
            doc.qp_motive = motive
            doc.qp_reject_is_invoice_error = is_invoice_error
            doc.save()
            _release_claimed_receipts(doc)
            resolve_open_alerts(doc.name)
            direct_rejected.append(doc.name)
            continue
        doc.qp_reject_orig_state = doc.nvfac_esta
        doc.nvfac_esta = "PR"
        doc.qp_motive = motive
        doc.qp_reject_is_invoice_error = is_invoice_error
        initialize_event_schedule(doc, "R")
        doc.save()
        _release_claimed_receipts(doc)
        rejects.append({
            "doc": doc.name,
            "motive": motive,
            "rule": doc.qp_auto_reject_rule or None,
        })

    frappe.db.commit()

    enqueue_error = None
    if rejects:
        try:
            for item in rejects:
                schedule_event(item["doc"])
        except Exception as error:
            # El estado ya quedo commiteado ("PR"); un fallo de encolado no
            # debe responder error contradictorio. Se registra y se alerta:
            # el ciclo automatico (run_auto_reject) retomara los "PR".
            enqueue_error = str(error)
            frappe.log_error(
                message=frappe.get_traceback(),
                title="Rechazo documenteme - fallo de encolado",
            )
            for item in rejects:
                insert_alert(
                    item["doc"],
                    "No se pudo encolar el rechazo; se reintentara en la "
                    "proxima ejecucion automatica.",
                    _make_now(),
                    alert_type="ErrorUrgente",
                )
            frappe.db.commit()

    if not rejects:
        response(
            200,
            "Rechazo completado",
            {"rejected": direct_rejected, "in_process": []},
        )
        return

    in_process = [item["doc"] for item in rejects]
    breakdown = {"rejected": direct_rejected, "in_process": in_process}

    if enqueue_error:
        breakdown["enqueue_error"] = enqueue_error
        response(
            200,
            "El rechazo quedo registrado, pero no se pudo iniciar el envio a "
            "documenteme; se reintentara automaticamente.",
            breakdown,
        )
        return

    if len(doc_names) == 1:
        message = "Rechazo en proceso para la factura"
    else:
        message = "Rechazo en proceso para las {} facturas".format(len(doc_names))
    response(200, message, breakdown)
