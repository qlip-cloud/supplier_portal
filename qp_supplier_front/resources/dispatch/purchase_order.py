import frappe
import json
from qp_supplier_front.uses_cases.dispatch.purchase_order_create import handler as create_purchase_order
from qp_supplier_front.uses_cases.dispatch.purchase_order_create_by_filters import handler as create_by_filter_purchase_order 
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.get_data import get_dynamic_link
from qp_supplier_front.services.pagination import get_paginated


@frappe.whitelist()
def create(supplier_id, dispatchs):
    
    method = frappe.local.request.method
    
    try:
        dispatchs = json.loads(dispatchs)    
        msg = "Los datos han sido creados correctamente"
        
        create_purchase_order(supplier_id, dispatchs)
        
        list_dispatch = get_list_dispatch(supplier_id)
        
        response(200, msg, list_dispatch)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500, msg)
        
@frappe.whitelist()
def create_by_filter(supplier_id, filters):
    
    method = frappe.local.request.method
    
    try:
        filters = json.loads(filters)    
        msg = "Los datos han sido creados correctamente"
        
        create_by_filter_purchase_order(supplier_id, filters)
        
        list_dispatch = get_list_dispatch(supplier_id)
        
        response(200, msg, list_dispatch)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500, msg)
        
def get_list_dispatch(supplier_id):
    
    doctype = "qp_SP_Dispatch"

    dispatchs = get_paginated(0, doctype, supplier_id, "travel_date", filters = {"is_complete": False} )
    
    return frappe.render_template("qp_supplier_front/templates/list/dispatch/list.html", {
        "dispatch": dispatchs
    })