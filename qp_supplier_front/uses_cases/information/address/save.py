
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_dynamic_link, get_party
from qp_supplier_front.services.field_validate import validate_field_list

def handler(supplier_id, country, city, state, address_line1):
    
    doctype = "Address"
    
    valid_code = "address"
    
    supplier = get_supplier(supplier_id)
    
    address = create_address(supplier, doctype, country, city, state, address_line1)
    
    fields_to_validate = ['address_line1', 'city', 'country', 'state']
    
    validate_field_list(supplier,doctype, valid_code, fields_to_validate)
    
    supplier.save()
    
    return {
        "address": address.as_dict(),
        "supplier": supplier,
    }

def create_address(supplier, doctype, country, city, state, address_line1):
    
    address = frappe.new_doc(doctype)
    
    address.address_line1 = address_line1
    address.city = city
    address.country = country
    address.state = state
    address.append("links", {
		"link_doctype": supplier.doctype,
		"link_name": supplier.name
	})
    
    if not get_dynamic_link(supplier, doctype):
        
        save_party(supplier, country, city, state)
        
        address.is_primary_address = 1
    
    address.insert()
    
    return address
    
def save_party(supplier, country, state, municipality):
    
    party = get_party(supplier)
    
    party.country = country
    party.state = state
    party.municipality = municipality
        
    party.save()
         
