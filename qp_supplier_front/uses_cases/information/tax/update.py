
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_party
from qp_supplier_front.services.field_validate import handler as validate_field
def handler(supplier_id, qp_vat_officer, tax_regime, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, ciiu_id, qp_resolution):
    
    supplier = get_supplier(supplier_id)
    
    set_tax(supplier, qp_vat_officer, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, qp_resolution)
    
    save_party(supplier, tax_regime, ciiu_id)
    
    validate_field(supplier, "tax" , 0, None,qp_vat_officer, tax_regime, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, ciiu_id, qp_resolution)
    
    supplier.save()
    
    return {
        "supplier": supplier.as_dict()
    }
    
def  set_tax(supplier, qp_vat_officer, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, qp_resolution):
    
    supplier.qp_vat_officer = qp_vat_officer
    supplier.qp_industry_and_commerce_tax = qp_industry_and_commerce_tax
    supplier.qp_industry_and_commerce_rate = qp_industry_and_commerce_rate
    supplier.qp_self_retaining = qp_self_retaining
    supplier.qp_major_contributor = qp_major_contributor
    supplier.qp_vat_withholding_agent = qp_vat_withholding_agent
    supplier.qp_resolution = qp_resolution
    
    
def save_party(supplier, tax_regime, ciiu_id):
    
    party = get_party(supplier)
    
    party.tax_regime = tax_regime
    party.ciiu_id = ciiu_id
        
    party.save()