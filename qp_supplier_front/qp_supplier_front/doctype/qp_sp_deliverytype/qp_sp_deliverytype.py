# -*- coding: utf-8 -*-
from frappe.model.document import Document


class qp_SP_DeliveryType(Document):

    def validate(self):
        if self.title:
            self.title = self.title.strip()
        if self.code:
            self.code = self.code.strip()
        if self.description:
            self.description = self.description.strip()
