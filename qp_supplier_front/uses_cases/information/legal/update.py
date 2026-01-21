
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import handler as validate_field
def handler(supplier_id, qp_legal_name, qp_legal_id_type, qp_legal_tax_id, qp_legal_place_expedition, qp_legal_date_expedition):
    
    supplier = get_supplier(supplier_id)
    
    set_legal(supplier, qp_legal_name, qp_legal_id_type, qp_legal_tax_id, qp_legal_place_expedition, qp_legal_date_expedition)
    
    validate_field(supplier, "legal" , 0, None, qp_legal_name=qp_legal_name, qp_legal_id_type=qp_legal_id_type, qp_legal_tax_id=qp_legal_tax_id, qp_legal_place_expedition=qp_legal_place_expedition, qp_legal_date_expedition=qp_legal_date_expedition)
        
    return {
        "supplier": supplier.as_dict()
    }
    
def  set_legal(supplier, qp_legal_name, qp_legal_id_type, qp_legal_tax_id, qp_legal_place_expedition, qp_legal_date_expedition):
    
    if qp_legal_name and qp_legal_name.strip() != "":
    
        supplier.qp_legal_name = qp_legal_name
        
    if qp_legal_tax_id and qp_legal_tax_id.strip() not in ["", "0"]:
        
        supplier.qp_legal_id_type = qp_legal_id_type
    
    if qp_legal_tax_id and qp_legal_tax_id.strip() != "":
        
        supplier.qp_legal_tax_id = qp_legal_tax_id
        
    if qp_legal_place_expedition and qp_legal_place_expedition.strip() != "":
    
        supplier.qp_legal_place_expedition = qp_legal_place_expedition
        
    if qp_legal_date_expedition and qp_legal_date_expedition.strip() != "":
        
        supplier.qp_legal_date_expedition = qp_legal_date_expedition
    