import frappe
from qp_supplier_front.uses_cases.information.contact.save import handler as save_contact   
from qp_supplier_front.uses_cases.information.contact.update import handler as update_contact   
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.information.contact.get import get_contact
from qp_supplier_front.services.get_data import get_dynamic_link


@frappe.whitelist()
def save(supplier_id, first_name,  qp_contact_type, email_id,country_code,phone, doctype_id = None):
    
    method = frappe.local.request.method
    try:
        
        msg = "Los datos han sido creados correctamente"
        full_phone = f"{country_code or ''} {phone or ''}".strip()
        if method == "POST":
        
            result = save_contact(supplier_id, first_name,email_id, qp_contact_type , full_phone)
            
        elif method == "PUT":
            
            result = update_contact(supplier_id, doctype_id, first_name,email_id, qp_contact_type , full_phone)
            
        contacts = get_dynamic_link(result.get("supplier"), "Contact")
        
        list = frappe.render_template("qp_supplier_front/templates/list/information/contacts.html", {
            "contacts": contacts
        })
        
        result.setdefault("render", {"list": list, "container": "contact_list"})
            
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear contacto: {str(error)}"
        
        response(500,  msg)

@frappe.whitelist()
def search_contact(contact_id):
    
    try:
        
        msg = "Los datos han sido buscados correctamente"
        
        result = get_contact(contact_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al buscados contacto: {str(error)}"
        
        response(500,  msg)   
    
        
