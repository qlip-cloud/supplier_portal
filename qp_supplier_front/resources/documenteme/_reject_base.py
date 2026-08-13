import frappe
from frappe import parse_json
from datetime import datetime
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._alerts import resolve_open_alerts
from qp_supplier_front.uses_cases.documenteme.reject import reject_document
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
    doc_names = parse_json(doc_names_raw)
    is_invoice_error = parse_json(is_invoice_error_raw)

    if not _has_permission(frappe.get_roles()):
        response(403, "No tiene permisos para rechazar facturas")
        return

    for doc_name in doc_names:
        reject_document(
            doc_name,
            motive,
            is_invoice_error,
            get_doc_fn=frappe.get_doc,
            send_request_fn=send_request_fn,
            commit_fn=frappe.db.commit,
            get_company_tax_id_fn=_get_company_tax_id,
            now_fn=_make_now,
        )
        resolve_open_alerts(doc_name)

    response(200, "Factura(s) rechazada(s) correctamente")