import json
import frappe
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.dispatch.find_detail_filter_lot import handler as find_detail_filter_lot   
from qp_supplier_front.uses_cases.dispatch.find_with_error_filter import handler as find_with_error_filter   

@frappe.whitelist()
def search_detail_filter_lot(supplier_id, filters):
       
    try:
        filters = json.loads(filters)

        msg = "Los datos han sido creados correctamente"
        
        result = find_detail_filter_lot(supplier_id, filters)
        
        response(200, msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500, msg)
        
@frappe.whitelist()
def search_error_filter(supplier_id, filters):
    
    try:
        filters = json.loads(filters)

        msg = "Los datos han sido buscados correctamente"
        
        result = find_with_error_filter(supplier_id, filters)
        
        template = frappe.render_template(f"qp_supplier_front/templates/list/dispatch/error_list.html", {"errors": result})
        
        data = {"total_errors": len(result), "template": template}
        
        response(200, msg, data)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500, msg)
        