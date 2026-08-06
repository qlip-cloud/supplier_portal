# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class qp_SP_AssignmentConfig(Document):

    def validate(self):
        if self.headquarter:
            self.headquarter = self.headquarter.strip()
        if self.oc_type:
            self.oc_type = self.oc_type.strip()

        if not self.headquarter and not self.oc_type:
            frappe.throw(
                "Debe indicar una sede o un tipo de OC para la configuracion"
            )
