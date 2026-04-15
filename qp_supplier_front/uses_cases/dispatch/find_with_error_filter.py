import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request_status
from qp_supplier_front.constant.endpoint import DISPATCH_PURCHASE_ORDER_CREATE

def handler(supplier_id, filters):
    
    del filters["is_complete"]
    
    filters.setdefault("supplier_id", supplier_id)
    
    filters.setdefault("is_error", True)
    
    result = frappe.get_list("qp_SP_DispatchSync", filters = filters ,fields = ["travel_id"], group_by='travel_id', order_by = "travel_id asc")
    
    return result