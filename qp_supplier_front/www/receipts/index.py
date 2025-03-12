import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import PAYMENT_SUPPLIER_ID
from qp_supplier_front.services.pagination import save_to_redis, get_paginated

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    param = supplier_id
    
    result = send_request(PAYMENT_SUPPLIER_ID, param = param)
    
    receipts = []
    
    key = f"receipts:{supplier_id}"
    
    if "status" in result and result.get("status") == 200:
        
        payments = result.get("payments", [])
    
        save_to_redis(payments, key)
        
        receipts = get_paginated(1, key)
    
    context.receipts = receipts
    
    context.key = key
    
