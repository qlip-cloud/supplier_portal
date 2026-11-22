# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from qp_supplier_front.services.sede_source import list_sedes as _list_sedes
from qp_supplier_front.uses_cases.documenteme.no_purchase_order import (
    INVOICE_TYPE_ALL,
    INVOICE_TYPE_CASH,
    INVOICE_TYPE_CREDIT,
)

NO_APLICA = "No aplica"

INVOICE_TYPES = (INVOICE_TYPE_ALL, INVOICE_TYPE_CREDIT, INVOICE_TYPE_CASH)


@frappe.whitelist()
def get_assignment_config_options():
    try:
        sedes = _list_sedes()
        oc_types = frappe.get_all(
            "qp_SP_OCType",
            fields=["name", "oc_type"],
            order_by="oc_type asc",
        )
        return {
            "sedes": [
                {
                    "value": sede.get("code"),
                    "label": _format_sede_label(sede),
                }
                for sede in (sedes or [])
                if sede.get("code")
            ],
            "oc_types": [
                {"value": NO_APLICA, "label": NO_APLICA}
            ] + [
                {"value": row.get("name"), "label": row.get("oc_type")}
                for row in (oc_types or [])
                if row.get("name") and row.get("oc_type")
            ],
        }
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "qp_SP_AssignmentConfig get options"
        )
        return {"sedes": [], "oc_types": []}


def _format_sede_label(sede):
    code = sede.get("code")
    title = sede.get("title")
    if title:
        return "{0} ({1})".format(title, code)
    return code


def _normalize_headquarter(value):
    """Normaliza headquarter a solo el codigo (descarta label tras \\n)."""
    if not value:
        return ""
    return value.split("\n", 1)[0].strip()


def _normalize_oc_type(value, oc_type_rows):
    """Normaliza oc_type al codigo (name del registro de qp_SP_OCType).

    Acepta el label texto (ej. "01 INFRAESTRUCTURA"), el codigo (name)
    o un valor legacy pre-configurado y devuelve el codigo (name).
    Rows esperados: [{"name": ..., "oc_type": ...}].
    """
    value = (value or "").strip()
    if not value:
        return ""
    for row in (oc_type_rows or []):
        if value == row.get("name") or value == row.get("oc_type"):
            return row.get("name")
    return value


class qp_SP_AssignmentConfig(Document):

    def validate(self):
        self.oc_type = (self.oc_type or "").strip()
        self.headquarter = _normalize_headquarter(self.headquarter)
        self.invoice_type = (self.invoice_type or "").strip() or INVOICE_TYPE_ALL
        if self.invoice_type not in INVOICE_TYPES:
            self.invoice_type = INVOICE_TYPE_ALL

        # "No aplica": fila wildcard que se asigna sin importar OC type ni
        # headquarter (tambien cubre el contado sin OC).
        if self.oc_type == NO_APLICA:
            return

        # Fila catch-all: oc_type y headquarter vacios. Se exige el tipo de
        # factura para no compartir destinatarios entre contado y credito.
        if not self.oc_type and not self.headquarter:
            if self.invoice_type not in (INVOICE_TYPE_CREDIT, INVOICE_TYPE_CASH):
                frappe.throw(
                    "Debe indicar el tipo de factura (Credito o Contado) para "
                    "la configuracion sin OC"
                )
            return

        if not self.oc_type:
            frappe.throw("Debe indicar el tipo de OC para la configuracion")

        oc_type_rows = frappe.get_all("qp_SP_OCType", fields=["name", "oc_type"])
        self.oc_type = _normalize_oc_type(self.oc_type, oc_type_rows)

        inventariable = frappe.db.get_value(
            "qp_SP_OCType", {"name": self.oc_type}, "is_inventariable"
        )
        if inventariable and not self.headquarter:
            frappe.throw("El tipo de OC inventariable requiere una sede")
