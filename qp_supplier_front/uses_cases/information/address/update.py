
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import validate_field_list

def handler(supplier_id, address_id, country, city, state, address_line1):
    
    doctype = "Address"
    
    valid_code = "address"
    
    supplier = get_supplier(supplier_id)
    
    address = update_address(doctype,address_id, country, city, state, address_line1)
    
    fields_to_validate = ['address_line1', 'city', 'country', 'state']
    
    validate_field_list(supplier,doctype, valid_code, fields_to_validate)
    
    supplier.save()
    
    return {
        "address": address.as_dict()
    }

def  update_address(doctype, address_id, country, city, state, address_line1):
    
    address = frappe.get_doc(doctype, address_id)
    
    address.address_line1 = address_line1
    address.city = city
    address.country = country
    address.state = state
   
    address.save()
    
    return address
    
         
