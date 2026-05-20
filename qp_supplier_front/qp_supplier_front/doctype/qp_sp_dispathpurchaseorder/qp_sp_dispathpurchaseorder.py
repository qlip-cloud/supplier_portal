# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from datetime import datetime
class qp_SP_DispathPurchaseOrder(Document):

	def init(self, *args, **kwargs):
     
		self.purchase_type = 1
		self.document_date = datetime.today()
		self.trade_discount_amount = 0
		self.freight_amount = 0
		self.miscellaneous_amount = 0
		self.currency_id = "COP"
		self.required_date = datetime.today()
  
	def set_bol_details(self, dispatchs, item_number):
		
		for dispatch in dispatchs:
			
   			self.append("bol_details",{
				"dispatch": dispatch.get("name"),
				"location": "",
				"item_number": item_number,
				"required_date": datetime.today(),
				"promised_date":  datetime.today()
			})
		
