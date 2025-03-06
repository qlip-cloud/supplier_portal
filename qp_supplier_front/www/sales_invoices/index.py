import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import INVOICE_SUPPLIER_ID
from qp_supplier_front.services.pagination import save_to_redis, get_paginated

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    param = supplier_id
    
    result = send_request(INVOICE_SUPPLIER_ID, param=param)
    
    sales_invoices = []
    
    key = f"sales_invoices:{supplier_id}"
    
    if "status" in result and result.get("status") == 200:
        
        invoices = result.get('invoices', [])
    
        save_to_redis(invoices, key)
    
        sales_invoices = get_paginated(1, key)
        
    context.sales_invoices = sales_invoices
    
    context.key = key
    
    
