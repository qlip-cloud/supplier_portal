import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request_status
from qp_supplier_front.constant.endpoint import DISPATCH_PURCHASE_ORDER_CREATE

def handler(supplier_id, filters):
        
    filters.setdefault("supplier", supplier_id)
    
    result = frappe.get_list("qp_SP_Dispatch", filters = filters, fields = ["count(name) as count, sum(travel_amount) as total"])
    
    assert_has_result(result)
    
    return result[0]
    
def assert_has_result(result):
    
    if not result or not result[0].get("count"):
        
        frappe.throw("No hay despachos que cumplan las condiciones")