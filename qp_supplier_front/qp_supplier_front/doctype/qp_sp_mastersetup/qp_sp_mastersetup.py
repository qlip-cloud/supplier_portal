# Copyright (c) 2025, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class qp_SP_MasterSetup(Document):

	def validate(self):
		if self.get("documenteme_simulation") and not frappe.session.user == "Administrator":
			frappe.throw(
				"El modo simulador documenteme solo puede activarse por el Administrador."
			)
