import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import PAYMENT_ALL
from qp_supplier_front.services.pagination import save_to_redis, get_paginated

def get_context(context):
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    result = send_request(PAYMENT_ALL)
    
    payments = result.get("payments", [])
    
    key = "receipts"
    
    save_to_redis(payments, key)
    
    context.receipts = get_paginated(1, key)
    
    context.key = key
    
