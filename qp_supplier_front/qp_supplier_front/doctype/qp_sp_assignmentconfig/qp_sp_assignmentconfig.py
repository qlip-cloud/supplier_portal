# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


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
