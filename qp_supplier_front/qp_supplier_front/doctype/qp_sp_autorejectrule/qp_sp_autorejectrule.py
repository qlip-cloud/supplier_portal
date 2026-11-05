# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class qp_SP_AutoRejectRule(Document):

    def validate(self):
        if self.rule_code:
            self.rule_code = self.rule_code.strip()
        if self.rule_name:
            self.rule_name = self.rule_name.strip()
