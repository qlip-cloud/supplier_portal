
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_dynamic_link
from qp_supplier_front.services.field_validate import validate_field_list_with_table

def handler(supplier_id, first_name, email_id, phone):
    
    doctype = "Contact"
    
    valid_code = "contact"
    
    supplier = get_supplier(supplier_id)
    
    contact = create_contact(supplier, doctype, first_name, email_id, phone)
    
    tables = {
        "email_ids": ["email_id"],
        "phone_nos": ["phone"]
    }
    
    fields_to_validate = ['first_name']
    
    validate_field_list_with_table(supplier, doctype, valid_code, fields_to_validate, tables)
    
    supplier.save()
    
    return {
        "contact": contact.as_dict()
    }
    
def  create_contact(supplier, doctype, first_name, email_id, phone):
    
    
    contact = frappe.new_doc(doctype)
    
    contact.first_name = first_name
    
    contact.append("email_ids", {
        "email_id": email_id
    })
    
    contact.append("phone_nos", {
        "phone": phone
    })
    
    contact.append("links", {
		"link_doctype": supplier.doctype,
		"link_name": supplier.name
	})
    if not get_dynamic_link(supplier, doctype):
        
        contact.is_primary_contact = 1
    
    contact.insert()
    
    return contact
    
         
