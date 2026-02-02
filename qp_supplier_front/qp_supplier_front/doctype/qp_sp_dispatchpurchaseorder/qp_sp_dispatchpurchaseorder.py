# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today
import json
class qp_SP_DispatchPurchaseOrder(Document):

	def init(self, vendor_id, *args, **kwargs):
		self.set_new_name(self)
		self.purchase_number = self.name
		self.purchase_type = 1
		self.document_date = today()
		self.trade_discount_amount = 0
		self.freight_amount = 0
		self.miscellaneous_amount = 0
		self.currency_id = "COP"
		self.required_date = today()
		self.vendor_id = vendor_id
		self.comment_text = ""

	def set_bol_details(self, dispatchs, item_number):
		
		for dispatch in dispatchs:
      
			self.__assert_that_location_valid(dispatch.get("warehouse"), dispatch.get("name"))
   
			self.append("bol_details",{
				"dispatch": dispatch.get("name"),
				"location": dispatch.get("warehouse"),
				"item_number": item_number,
				"required_date": today(),
				"promised_date":  today()
			})
		
	def set_subtotal(self):
		
		self.subtotal = sum(map(lambda bol: bol.bol_value, self.bol_details))

	def set_payload(self):
		
		self.payload = self.__setup_payload()
  
	def __setup_payload(self):
     
		header = self.__get_header()

		bol_detail = self.__get_bol_detail()
  
		items = self.__get_items()
    
		return self.__get_payload_str(header, bol_detail, items)

	def __get_header(self):
		
		return {
			"PurchaseType": self.purchase_type,
			"PurchaseNumber": self.purchase_number,
			"VendorId": self.vendor_id,
			"DocumentDate": self.document_date,
			"TradeDiscountAmount": self.trade_discount_amount,
			"FreightAmount": self.freight_amount,
			"MiscellaneousAmount": self.miscellaneous_amount,
			"Subtotal": self.subtotal,
			"CommentText": self.comment_text,
			"CurrencyId": self.currency_id,
			"RequiredDate": self.required_date
		}

	def __get_bol_detail(self):
		
		return list(map(lambda line: 
			{
				 
				"Bol": line.bol,
				"Value": line.bol_value
				
			}
   		, self.bol_details))

	def __get_items(self):

		line = self.bol_details[0]
  
		return [
			{
				"Location": line.location,
				"ItemNumber": line.item_number,
				"Quantity": line.quantity,
				"RequiredDate": line.required_date,
				"PromisedDate": line.promised_date,
				"UnitCost": line.unitcost,
				"Uom": line.uom
			}]

	def __get_payload_str(self, header, bol_detail, items):
		
		header.setdefault("BolDetail", bol_detail)
  
		header.setdefault("Items", items)
  
		return json.dumps(header)

	def get_payload(self):
     
		return json.loads(self.payload)

	def save_is_error(self, response_internal):
     
		self.set_response(response_internal)
		self.set_is_error()
		self.save()
		
	def save_is_sync(self, response):
     
		self.set_response(response)
		self.set_is_sync()
		self.save()
  
	def set_response(self, response):
		self.response = response
  
	def set_is_error(self):
		
		self.is_error = True

	def set_is_sync(self):
		
		self.is_sync = True
		
	def __assert_that_location_valid(self, warehouse, line) :
		
		if not warehouse:
			
			frappe.throw(f"La linea {line} no tiene undeposito valido")