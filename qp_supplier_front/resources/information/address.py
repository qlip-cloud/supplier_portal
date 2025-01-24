import frappe
from qp_supplier_front.uses_cases.information.address.save import handler as save_address   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def save(supplier_id, country, city, state, address_line1):
    
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        result = save_address(supplier_id, country, city, state, address_line1)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500,  msg)
        
    
        
