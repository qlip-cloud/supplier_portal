import frappe
from qp_supplier_front.uses_cases.information.financial.update import handler as update_financial   
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.util.uppercase_utils import sanitize_colombian_number


@frappe.whitelist()
def update(supplier_id, qp_financial_assets, qp_financial_liabilities, qp_financial_equity, qp_financial_details_income, qp_financial_monthly_income, qp_financial_monthly_expenses, qp_financial_other_income):
    
    qp_financial_assets = sanitize_colombian_number(qp_financial_assets)
    qp_financial_liabilities = sanitize_colombian_number(qp_financial_liabilities)
    qp_financial_equity = sanitize_colombian_number(qp_financial_equity)
    qp_financial_other_income = sanitize_colombian_number(qp_financial_other_income)
    qp_financial_monthly_income = sanitize_colombian_number(qp_financial_monthly_income)
    qp_financial_monthly_expenses = sanitize_colombian_number(qp_financial_monthly_expenses)
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = update_financial(supplier_id, qp_financial_assets, qp_financial_liabilities, qp_financial_equity, qp_financial_details_income, qp_financial_monthly_income, qp_financial_monthly_expenses, qp_financial_other_income)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar informacion financiera: {str(error)}"
        
        response(500,  msg)
        
    
        
