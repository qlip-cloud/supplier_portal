import frappe
from qp_supplier_front.uses_cases.information.shareholder.update import handler as update_shareholder   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def update(supplier_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct):
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = update_shareholder(supplier_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Accionistas o Asociados: {str(error)}"
        
        response(500,  msg)
        
    
        
