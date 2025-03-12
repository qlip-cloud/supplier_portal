import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import ORDER_SUPPLIER_ID
from qp_supplier_front.services.pagination import save_to_redis, get_paginated

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    param = supplier_id
    
    result = send_request(ORDER_SUPPLIER_ID, param = param)
    
    key = f"sales_order:{supplier_id}"
    
    sales_order = []
    
    if "status" in result and result.get("status") == 200:
        
        orders = result.get("orders", [])
        
        save_to_redis(orders, key)
        
        sales_order = get_paginated(1, key)
    
    context.sales_order = sales_order
    
    context.key = key
    