import frappe
from qp_supplier_front.services.create_data import create_party, create_contact
from qp_supplier_front.services.field_validate import handler as validate_field


def handler(supplier_name, id_type_name, tax_id, phone_number, business_type_name): 
    
    supplier = create_supplier(supplier_name, tax_id)
    
    party = create_party(supplier, id_type_name, phone_number, business_type_name, tax_id)
    
    create_first_contact(supplier, phone_number)
    
    validate_field(supplier, "basic" , 0, None, supplier_name, id_type_name, tax_id, phone_number, business_type_name)
    
    return {
        "supplier": supplier.as_dict(),
        "party": party.as_dict(),
        "redirect_to": "information?supplier=" + supplier.name
    }    
    
def create_supplier(supplier_name, tax_id):
    
    supplier = frappe.new_doc("Supplier")
    
    supplier.supplier_name = supplier_name
    
    supplier.tax_id = tax_id
    
    supplier.supplier_group = "Todos los grupos de proveedores"
    
    supplier.insert()
    
    return supplier

def create_first_contact(supplier, phone_number):
    
    doctype = "Contact"
    
    user = frappe.session.user
    
    contact = create_contact(supplier, doctype, supplier.supplier_name, user, phone_number , user)
    
    return contact
     