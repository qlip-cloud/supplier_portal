import frappe
from qp_supplier_front.services.pagination import get_paginated
from qp_supplier_front.resources.response import handler as response

@frappe.whitelist()
def render_pagination(page, key):
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        pagination = get_paginated(int(page), key)
        
        template = frappe.render_template(f"qp_supplier_front/templates/form/{key}/list.html", {
                    key: pagination
                })
            
        response(200,  msg, template)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500,  msg)