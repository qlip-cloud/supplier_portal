import frappe
import json
from qp_supplier_front.uses_cases.dispatch.sync_by_supplier import handler as sync_by_supplier
from qp_supplier_front.services.pagination import get_paginated
from qp_supplier_front.services.get_data import has_recent_news
from qp_supplier_front.services.get_data import get_has_dispatch_permission


DOCTYPE = "qp_SP_Dispatch"

ORDER_BY = "travel_date"

def get_context(context):
    
    context.no_cache = True
    
    supplier_id = get_supplier_id()
    
    setup_context_default(context, supplier_id)
    
    assert_that_supplier_has_dispatch_permission(context)
    
    launch_sync(supplier_id)
    
    origins = frappe.get_list("qp_SP_DispatchWarehouse", fields = ["title"])
    
    dispatch = get_paginated(0, DOCTYPE, supplier_id, ORDER_BY, filters = {"is_complete": False})
    
    set_context(context, origins, dispatch)

def setup_context_default(context, supplier_id):
    
    context.supplier_id = supplier_id
    
    context.has_recent_news = has_recent_news()
    
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
    
def assert_that_supplier_has_dispatch_permission(context):
    
    if not context.has_dispatch_permission:
        
        context.is_error = True
        
        context.error_msg = "No tiene permiso para ver esta seccion"
        
        frappe.throw(context.error_msg)
        
def get_supplier_id():
    
    query_params = frappe.request.args
    
    return query_params.get("supplier")
    
def launch_sync(supplier_id):
    
    try:
        sync_by_supplier(supplier_id)
        
    except Exception as e:
        
        frappe.log_error(message=frappe.get_traceback(), title=f"Error sync dispath: {supplier_id}")
            
def set_context(context, origins, dispatch):

    context.origins = origins
    
    context.dispatch = dispatch
    
    context.order_by = ORDER_BY
                               
    context.key = "dispatch"
    
    context.doctype = DOCTYPE
        
    context.show_result = True
    
    context.date_key = ORDER_BY