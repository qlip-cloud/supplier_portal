# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class qp_SP_OCType(Document):

    def validate(self):
        if self.oc_type:
            self.oc_type = self.oc_type.strip()
