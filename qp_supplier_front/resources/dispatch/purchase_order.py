import frappe
import json
from qp_supplier_front.uses_cases.dispatch.purchase_order_create import handler as create_purchase_order   
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
        
        doctype = "qp_SP_Dispatch"

        dispatchs = get_paginated(0, doctype, supplier_id, "creation", filters = {"is_complete": False} )
        
        list_dispatch = frappe.render_template("qp_supplier_front/templates/list/dispatch/list.html", {
            "dispatch": dispatchs
        })
        
        response(200, msg, list_dispatch)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500, msg)
        