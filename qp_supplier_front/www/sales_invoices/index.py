import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import INVOICE_ALL
from qp_supplier_front.services.pagination import save_to_redis, get_paginated

def get_context(context):
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    result = send_request(INVOICE_ALL)
    
    invoices = result.get('invoices', [])
    
    key ="sales_invoices"
    
    save_to_redis(invoices, key)
    
    context.sales_invoices = get_paginated(1, key)
    
    context.key = key
    
    
