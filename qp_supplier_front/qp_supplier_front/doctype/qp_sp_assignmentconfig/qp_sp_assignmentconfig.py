# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from qp_supplier_front.services.sede_source import list_sedes as _list_sedes


@frappe.whitelist()
def get_assignment_config_options():
    try:
        sedes = _list_sedes()
        oc_types = frappe.get_all(
            "qp_SP_OCType",
            fields=["oc_type"],
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
            "oc_types": [row.get("oc_type") for row in (oc_types or []) if row.get("oc_type")],
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


class qp_SP_AssignmentConfig(Document):

    def validate(self):
        self.oc_type = (self.oc_type or "").strip()
        self.headquarter = (self.headquarter or "").strip()

        if not self.oc_type:
            frappe.throw("Debe indicar el tipo de OC para la configuracion")

        inventariable = frappe.db.get_value(
            "qp_SP_OCType", {"oc_type": self.oc_type}, "is_inventariable"
        )
        if inventariable and not self.headquarter:
            frappe.throw("El tipo de OC inventariable requiere una sede")
