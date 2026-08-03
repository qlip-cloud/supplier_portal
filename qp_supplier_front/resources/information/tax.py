import frappe
from qp_supplier_front.uses_cases.information.tax.update import handler as update_tax   
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.util.uppercase_utils import sanitize_colombian_number


@frappe.whitelist()
def update(supplier_id, qp_vat_officer, tax_regime, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, ciiu_id, qp_resolution, qp_resolution_self_retaining):
    
    qp_industry_and_commerce_rate = sanitize_colombian_number(qp_industry_and_commerce_rate)
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = update_tax(supplier_id, qp_vat_officer, tax_regime, qp_industry_and_commerce_tax, qp_industry_and_commerce_rate, qp_self_retaining, qp_major_contributor, qp_vat_withholding_agent, ciiu_id, qp_resolution, qp_resolution_self_retaining)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Información Tributaria: {str(error)}"
        
        response(500,  msg)
        
    
        
