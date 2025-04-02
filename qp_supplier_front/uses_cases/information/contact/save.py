
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import validate_field_list_with_table
from qp_supplier_front.services.create_data import create_contact

def handler(supplier_id, first_name,email_id, qp_contact_type,phone):
    
    doctype = "Contact"
    
    valid_code = "contact"
    
    supplier = get_supplier(supplier_id)
    
    contact = create_contact(supplier, doctype, first_name,email_id, qp_contact_type,phone)
    
    tables = {
        "email_ids": ["email_id"],
        "phone_nos": ["phone"]
    }
    
    fields_to_validate = ['first_name']
    
    validate_field_list_with_table(supplier, doctype, valid_code, fields_to_validate, tables)
    
    supplier.save()
    
    return {
        "contact": contact.as_dict(),
        "supplier": supplier

    }
    

    
         
