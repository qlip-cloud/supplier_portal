
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_dynamic_link
from qp_supplier_front.services.field_validate import validate_field_list_with_table

def handler(supplier_id, doctype_id, first_name,email_id, qp_contact_type,phone):
    
    doctype = "Contact"
    
    valid_code = "contact"
    
    supplier = get_supplier(supplier_id)
    
    contact = update_contact(doctype_id, doctype, first_name,email_id, qp_contact_type ,phone)
    
    tables = {
        "email_ids": ["email_id"],
        "phone_nos": ["phone"],
    }
    
    fields_to_validate = ['first_name']
    
    validate_field_list_with_table(supplier, doctype, valid_code, fields_to_validate, tables)
    
    supplier.save()
    
    return {
        "contact": contact.as_dict(),
        "supplier": supplier
    }
    
def  update_contact(doctype_id, doctype, first_name, email_id, qp_contact_type ,phone):
    
    
    contact = frappe.get_doc(doctype, doctype_id)
    
    contact.first_name = first_name
    contact.qp_contact_type = qp_contact_type
    contact.email_ids = []
    contact.phone_nos = []
    
    contact.append("email_ids", {
        "email_id": email_id
    })
    
    contact.append("phone_nos", {
        "phone": phone
    })
    
    
    contact.flags.ignore_links = True
    contact.save()
    
    return contact
    
         
