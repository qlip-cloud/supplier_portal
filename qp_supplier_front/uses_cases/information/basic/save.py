import frappe
from qp_supplier_front.services.create_data import create_party, create_first_contact
from qp_supplier_front.services.field_validate import handler as validate_field


def handler(supplier_name, id_type_name, tax_id, phone_number, business_type_name, qp_is_foreigner_supplier ,email = None): 
    
    supplier = create_supplier(supplier_name, tax_id, qp_is_foreigner_supplier)
    
    party = create_party(supplier, id_type_name, phone_number, business_type_name, tax_id, email)
    
    create_first_contact(supplier, email)
    
    validate_field(supplier, "basic" , 0, None, supplier_name, id_type_name, tax_id, phone_number, business_type_name)
    
    return {
        "supplier": supplier.as_dict(),
        "party": party.as_dict(),
        "redirect_to": "information?supplier=" + supplier.name
    }    
    
def create_supplier(supplier_name, tax_id, qp_is_foreigner_supplier,gp_vendor_id = None):
    
    supplier = frappe.new_doc("Supplier")
    
    supplier.supplier_name = supplier_name
    
    supplier.tax_id = tax_id
    
    supplier.gp_vendor_id = gp_vendor_id
    
    supplier.qp_asigned = True
    
    supplier.supplier_group = "Todos los grupos de proveedores"

    supplier.qp_is_foreigner_supplier =  True if qp_is_foreigner_supplier else False
    
    supplier.insert()
    
    return supplier     