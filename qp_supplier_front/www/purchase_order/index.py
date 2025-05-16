import frappe
import json
from qp_supplier_front.uses_cases.sales_order.sync_by_supplier import handler as sync_by_supplier_e
from qp_supplier_front.services.pagination import get_paginated

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    try:
        sync_by_supplier_e(supplier_id)
        
    except Exception as e:
        
        frappe.log_error(message=frappe.get_traceback(), title=f"Error sync purchase order: {supplier_id}")
            
    key = "sales_order"
    
    doctype = "Purchase Order"
    
    doctype_detail = "Purchase Order Item"
    
    context.order_by = "qp_create_date"
    
    context.supplier_id = supplier_id
    
    context.sales_order = get_paginated(0, doctype, supplier_id, context.order_by)
                       
    context.key = key
    
    context.doctype = doctype
    
    context.doctype_detail = doctype_detail
    
    context.show_result = True
    
    context.date_key = "qp_create_date"
    
    
