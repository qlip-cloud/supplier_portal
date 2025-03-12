import frappe
import json
from qp_supplier_front.services.pagination import get_paginated, get_detail
from qp_supplier_front.resources.response import handler as response

@frappe.whitelist()
def render_pagination(page, key, doctype, supplier_id, doctype_detail, filters = {}):
    try:
        
        msg = "Los datos han sido paginados correctamente"
        
        filters = json.loads(filters)
        
        pagination = get_paginated(int(page), doctype, supplier_id, filters)
        
        template = frappe.render_template(f"qp_supplier_front/templates/list/{key}/list.html", {
                    key: pagination, "doctype_detail":doctype_detail, "key": key
                })
            
        response(200,  msg, template)
        
    except Exception as error:
        
        msg = f"Error al paginar {doctype} para {supplier_id}: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def render_detail(key, doctype, name, page = 0):
    
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        detail = get_detail(doctype, name, int(page))
        
        template = frappe.render_template(f"qp_supplier_front/templates/list/{key}/list_detail.html", detail)
            
        response(200,  msg, template)
        
    except Exception as error:
        
        msg = f"Error al buscar {doctype} para {name}: {str(error)}"
        
        response(500,  msg)