import json
import frappe
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.dispatch.find_detail_filter_lot import handler as find_detail_filter_lot   

@frappe.whitelist()
def search_detail_filter_lot(supplier_id, filters):
    
    method = frappe.local.request.method
    
    try:
        filters = json.loads(filters)

        msg = "Los datos han sido creados correctamente"
        
        result = find_detail_filter_lot(supplier_id, filters)
        
        response(200, msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500, msg)
        