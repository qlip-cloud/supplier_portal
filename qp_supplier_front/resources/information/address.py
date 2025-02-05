import frappe
from qp_supplier_front.uses_cases.information.address.save import handler as save_address   
from qp_supplier_front.uses_cases.information.address.update import handler as update_address   
from qp_supplier_front.uses_cases.information.address.get import get_cities, get_states, get_address
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def save(supplier_id, country, city, state, address_line1, doctype_id = None):
    
    method = frappe.local.request.method
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        if method == "POST":
            
            result = save_address(supplier_id, country, city, state, address_line1)
            
        elif method == "PUT":
            
            result = update_address(supplier_id, doctype_id, country, city, state, address_line1)
            
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear direccion: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def search_cities(country):
    
    try:
        
        msg = "Los datos han sido buscados correctamente"
        
        result = get_cities(country)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al buscados ciudades: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def search_states(city):
    
    try:
        
        msg = "Los datos han sido buscados correctamente"
        
        result = get_states(city)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al buscados municipio: {str(error)}"
        
        response(500,  msg)
        
    
@frappe.whitelist()
def search_address(address_id):
    
    try:
        
        msg = "Los datos han sido buscados correctamente"
        
        result = get_address(address_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al buscados direccion: {str(error)}"
        
        response(500,  msg)     
