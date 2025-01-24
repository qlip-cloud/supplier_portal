import frappe
from qp_supplier_front.uses_cases.information.international.update import handler as update_international   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def update(supplier_id, qp_financial_currency_foreigner, qp_financial_which_currency_foreigner, qp_financial_other_operations, qp_financial_item_foreigner, qp_financial_account_currency_foreigner, qp_financial_item_type, qp_financial_item_number, qp_financial_entity, qp_financial_amount, qp_financial_city, qp_financial_country,qp_financial_currency):
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = update_international(supplier_id, qp_financial_currency_foreigner, qp_financial_which_currency_foreigner, qp_financial_other_operations, qp_financial_item_foreigner, qp_financial_account_currency_foreigner, qp_financial_item_type, qp_financial_item_number, qp_financial_entity, qp_financial_amount, qp_financial_city, qp_financial_country,qp_financial_currency)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar operaciones internacionales: {str(error)}"
        
        response(500,  msg)
        
    
        
