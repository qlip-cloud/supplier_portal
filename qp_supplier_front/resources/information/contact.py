import frappe
from qp_supplier_front.uses_cases.information.contact.save import handler as save_contact   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def save(supplier_id, first_name, email_id, phone):
    
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        result = save_contact(supplier_id, first_name, email_id, phone)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear contacto: {str(error)}"
        
        response(500,  msg)
        
    
        
