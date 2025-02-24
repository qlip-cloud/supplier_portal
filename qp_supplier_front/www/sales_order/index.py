import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import ORDER_ALL
from qp_supplier_front.services.pagination import save_to_redis, get_paginated

def get_context(context):
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    result = send_request(ORDER_ALL)
    
    orders = result.get("orders", [])
    
    key = "sales_order"
    
    save_to_redis(orders, key)
    
    context.sales_order = get_paginated(1, key)
    
    context.key = key
    