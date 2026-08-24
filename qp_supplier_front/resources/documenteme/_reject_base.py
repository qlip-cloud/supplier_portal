import frappe
from frappe import parse_json
from datetime import datetime
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._alerts import resolve_open_alerts
from qp_supplier_front.services.role_resolver import get_active_role

ALLOWED_ROLES = {"Administrador Documenteme", "Administrador Sede Documenteme"}


def _get_company_tax_id():
    company = frappe.get_doc("Company", frappe.defaults.get_user_default("company"))
    return company.tax_id


def _has_permission(user_roles):
    active = get_active_role(user_roles)
    return active in ALLOWED_ROLES


def _make_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_reject(doc_names_raw, motive, is_invoice_error_raw, send_request_fn):
    """Rechazo manual ASINCRONO.

    Marca cada factura como "PR" (En proceso de rechazo) persistiendo el
    motivo y el indicador de error, y encola el job de fondo que envia la
    secuencia 030 -> 032 -> 031 con reintentos hacia documenteme. No
    bloquea el servicio ni depende de la velocidad del servidor externo.
    """
    from qp_supplier_front.resources.documenteme.auto_reject import (
        REJECT_JOB_METHOD,
    )

    doc_names = parse_json(doc_names_raw)
    is_invoice_error = parse_json(is_invoice_error_raw)

    if not _has_permission(frappe.get_roles()):
        response(403, "No tiene permisos para rechazar facturas")
        return

    rejects = []
    for idx, doc_name in enumerate(doc_names):
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        doc.nvfac_esta = "PR"
        doc.qp_reject_orig_state = "E"
        doc.qp_motive = motive
        doc.qp_reject_is_invoice_error = is_invoice_error
        doc.save()
        rejects.append({
            "doc": doc_name,
            "motive": motive,
            "rule": doc.qp_auto_reject_rule or None,
        })

    frappe.db.commit()

    frappe.enqueue(
        REJECT_JOB_METHOD,
        rejects=rejects,
        queue="long",
        timeout=14400,
        job_name="reject documents ({})".format(len(rejects)),
    )

    if len(doc_names) == 1:
        message = "Rechazo en proceso para la factura"
    else:
        message = "Rechazo en proceso para las {} facturas".format(len(doc_names))
    response(200, message)
