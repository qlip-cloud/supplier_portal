import frappe
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id

    context.has_recent_news = has_recent_news()
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
    