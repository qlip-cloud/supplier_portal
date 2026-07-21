import frappe
from qp_supplier_front.services.get_data import get_party, get_supplier
from qp_supplier_front.services.create_data import create_party, set_party, update_primary_contact_phone
from qp_supplier_front.services.create_data import create_party, create_first_contact

from qp_supplier_front.services.field_validate import handler as validate_field, validar_supplier_name


def handler(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name, qp_is_foreigner_supplier):
    
    supplier = get_supplier(supplier_id)
    
    is_asigned = supplier.qp_asigned
    
    update_supplier(supplier, supplier_name, tax_id, qp_is_foreigner_supplier)
    
    if (not is_asigned):
    
        create_first_contact(supplier)
    
    party = save_or_create_party(supplier, id_type_name, phone_number, business_type_name, tax_id)
    
    update_primary_contact_phone(supplier, phone_number)
    
    validate_field(supplier, "basic" , 0, None, supplier_name=supplier_name, id_type_name=id_type_name, tax_id=tax_id, phone_number=phone_number, business_type_name=business_type_name)
    
    data = {
        "supplier": supplier.as_dict(),
        "party": party.as_dict()
    }   
    
    if (not is_asigned):
        
        data["redirect_to"] = "information?supplier=" + supplier.name
        
    return  data
    
def update_supplier(supplier, supplier_name, tax_id, qp_is_foreigner_supplier):
    
    validar_supplier_name(supplier_name)
    
    supplier.supplier_name = supplier_name
    
    supplier.tax_id = tax_id
    
    supplier.supplier_group = "Todos los grupos de proveedores"
    
    supplier.qp_asigned = True

    supplier.qp_is_foreigner_supplier = True if qp_is_foreigner_supplier else False
        
def save_or_create_party(supplier, id_type_name, phone_number, business_type_name, tax_id):
    
    party = get_party(supplier)
    
    if not party:
        
        return create_party(supplier, id_type_name, phone_number, business_type_name, tax_id)
                    
    set_party(party, supplier, id_type_name, phone_number, business_type_name, tax_id)
    
    party.save()
    
    return party
