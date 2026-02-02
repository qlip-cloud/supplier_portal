import frappe
import json
from qp_supplier_front.uses_cases.dispatch.sync_by_supplier import handler as sync_by_supplier
from qp_supplier_front.services.pagination import get_paginated
from qp_supplier_front.services.get_data import has_recent_news

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    try:
        sync_by_supplier(supplier_id)
        
    except Exception as e:
        
        frappe.log_error(message=frappe.get_traceback(), title=f"Error sync dispath: {supplier_id}")
    
    key = "dispatch"
    
    doctype = "qp_SP_Dispatch"
        
    context.order_by = "creation"
    
    context.supplier_id = supplier_id
    
    context.dispatch = get_paginated(0, doctype, supplier_id, context.order_by )
                       
    context.key = key
    
    context.doctype = doctype
        
    context.show_result = True
    
    context.date_key = "creation"

    context.has_recent_news = has_recent_news()
    
    
    