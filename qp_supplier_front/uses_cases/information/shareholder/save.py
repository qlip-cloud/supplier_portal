
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import setup_validate_field_list
def handler(supplier_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share):
    
    valid_code = "shareholder"
    
    supplier = get_supplier(supplier_id)
    
    set_shareholder(supplier, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share)
    
    fields_to_validate = ["fullname", "nationality", "have_resident_another_country", "have_american_visa", "id_type", "tax_id", "market_share"]
    
    setup_validate_field_list(supplier, supplier.qp_shareholders, valid_code, fields_to_validate)
    
    supplier.save()
    
    return {
        "supplier": supplier
    }
    
def  set_shareholder(supplier, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share):
    
    supplier.append("qp_shareholders", {
        "fullname" : fullname,
        "nationality" : nationality,
        "have_resident_another_country" : have_resident_another_country,
        "have_american_visa" : have_american_visa,
        "id_type" : id_type,
        "tax_id" : tax_id,
        "market_share" : market_share,
    })
    
    supplier.save()