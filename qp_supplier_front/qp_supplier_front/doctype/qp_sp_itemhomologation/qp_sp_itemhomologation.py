# -*- coding: utf-8 -*-
# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class qp_SP_ItemHomologation(Document):
	def validate(self):
		self._validate_unique_supplier_item_code()

	def _validate_unique_supplier_item_code(self):
		if not self.supplier or not self.supplier_item_code:
			return
		exists = frappe.db.exists(
			"qp_SP_ItemHomologation",
			{
				"supplier": self.supplier,
				"supplier_item_code": self.supplier_item_code,
				"name": ["!=", self.name or self.get("name")],
			},
		)
		if exists:
			frappe.throw(
				"Ya existe una homologacion para el proveedor {} y el codigo {}".format(
					self.supplier, self.supplier_item_code
				)
			)
