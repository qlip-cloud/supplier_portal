import frappe
from qp_supplier_front.services.get_data import get_party, get_supplier
from qp_supplier_front.services.field_validate import handler as validate_field


def handler(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name):
    
    supplier = get_supplier(supplier_id)
    
    update_supplier(supplier, supplier_name, tax_id)
    
    party = save_or_create_party(supplier, id_type_name, phone_number, business_type_name, tax_id)
    
    validate_field(supplier, "basic" , 0, None, supplier_name, id_type_name, tax_id, phone_number, business_type_name)
    
    return {
        "supplier": supplier.as_dict(),
        "party": party.as_dict()
    }    
    
def update_supplier(supplier, supplier_name, tax_id):
    
    supplier.supplier_name = supplier_name
    
    supplier.tax_id = tax_id
        
def save_or_create_party(supplier, id_type_name, phone_number, business_type_name, tax_id):
    
    party = get_party(supplier)
    
    if not party:
        
        return create_party(supplier, id_type_name, phone_number, business_type_name, tax_id)
                    
    set_party(party, supplier, id_type_name, phone_number, business_type_name, tax_id)
    
    party.save()
    
    return party
    
def create_party(supplier, id_type_name, phone_number, business_type_name, tax_id):
    
    party = frappe.new_doc("qp_CO_ThirdParty")
    
    set_party(party, supplier, id_type_name, phone_number, business_type_name, tax_id)
    
    party.insert()
    
    create_doctype_link(supplier, party)
    
    return party
        
def create_doctype_link(supplier, party):
    
    doctype = "DocType Link"
    
    doctype_link = frappe.new_doc(doctype)
    
    doctype_link.link_fieldname = supplier.name
    doctype_link.link_doctype = supplier.doctype
    doctype_link.parenttype = party.doctype
    doctype_link.parent = party.name
    
    doctype_link.insert()
    
    party.append(doctype, doctype_link)
    
    return doctype_link
    
def set_party(party, supplier, id_type_name, phone_number, business_type_name, tax_id):
    
    if not party.naming:
        
        party.naming = supplier.tax_id
    
        party.tax_id = supplier.tax_id
        
    party.first_name = supplier.supplier_name
    
    party.id_type = id_type_name
    
    party.phone_number = phone_number
    
    party.business_type = business_type_name