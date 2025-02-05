
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import setup_validate_field_list
def handler(supplier_id, doctype_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct):
    
    valid_code = "shareholder"
    
    
    update_shareholder(doctype_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct)
    
    fields_to_validate = ["fullname", "nationality", "have_resident_another_country", "have_american_visa", "id_type", "tax_id", "market_share", "authorization_data_processing", "supplier_code_conduct"]
    
    supplier = get_supplier(supplier_id)
    
    setup_validate_field_list(supplier, supplier.qp_shareholders, valid_code, fields_to_validate)
    
    supplier.save()
    
    return {
        "supplier": supplier.as_dict()
    }
    
def  update_shareholder(doctype_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct):
    
    shareholder = frappe.get_doc("qp_SP_ShareHolder",doctype_id)
    
    shareholder.fullname = fullname
    shareholder.nationality = nationality
    shareholder.have_resident_another_country = have_resident_another_country
    shareholder.have_american_visa = have_american_visa
    shareholder.id_type = id_type
    shareholder.tax_id = tax_id
    shareholder.market_share = market_share
    shareholder.authorization_data_processing = authorization_data_processing
    shareholder.supplier_code_conduct = supplier_code_conduct

    
    shareholder.save()