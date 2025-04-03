
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_party
from qp_supplier_front.services.field_validate import handler as validate_field
def handler(supplier_id, qp_vat_officer, tax_regime, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, ciiu_id, qp_resolution, qp_resolution_self_retaining):
    
    supplier = get_supplier(supplier_id)
    
    set_tax(supplier, qp_vat_officer, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, qp_resolution, qp_resolution_self_retaining)
    
    save_party(supplier, tax_regime, ciiu_id)
    
    validate_field(supplier, "tax" , 0, None,qp_vat_officer, tax_regime, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, ciiu_id, qp_resolution, qp_resolution_self_retaining)
        
    return {
        "supplier": supplier.as_dict()
    }
    
def  set_tax(supplier, qp_vat_officer, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, qp_resolution, qp_resolution_self_retaining):
    
    supplier.qp_vat_officer = qp_vat_officer
    supplier.qp_industry_and_commerce_tax = qp_industry_and_commerce_tax
    supplier.qp_industry_and_commerce_rate = qp_industry_and_commerce_rate
    supplier.qp_self_retaining = qp_self_retaining
    supplier.qp_major_contributor = qp_major_contributor
    supplier.qp_vat_withholding_agent = qp_vat_withholding_agent
    supplier.qp_resolution = qp_resolution
    supplier.qp_resolution_self_retaining = qp_resolution_self_retaining
    
    
def save_party(supplier, tax_regime, ciiu_id):
    
    party = get_party(supplier)
    
    if tax_regime and tax_regime.strip() not in ["", "0"]:
    
        party.tax_regime = tax_regime
        
    if ciiu_id and ciiu_id.strip() not in ["", "0"]:
    
        party.ciiu_id = ciiu_id
        
    party.save()