import frappe
import json

from qp_supplier_front.uses_cases.dispatch.purchase_order_create import handler as create_purchase_order

def handler(supplier_id, filters):
    
    dispatchs_id = frappe.get_list("qp_SP_Dispatch", filters = filters, pluck = "name")
    
    create_purchase_order(supplier_id, dispatchs_id)