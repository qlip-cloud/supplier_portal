
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import handler as validate_field
def handler(supplier_id, qp_financial_assets, qp_financial_liabilities, qp_financial_equity, qp_financial_details_income, qp_financial_monthly_income, qp_financial_monthly_expenses, qp_financial_other_income):
    
    supplier = get_supplier(supplier_id)
    
    set_financial(supplier, qp_financial_assets, qp_financial_liabilities, qp_financial_equity, qp_financial_details_income, qp_financial_monthly_income, qp_financial_monthly_expenses, qp_financial_other_income)
    
    validate_field(supplier, "financial" , 0, None, qp_financial_assets=qp_financial_assets, qp_financial_liabilities=qp_financial_liabilities, qp_financial_equity=qp_financial_equity, qp_financial_details_income=qp_financial_details_income, qp_financial_monthly_income=qp_financial_monthly_income, qp_financial_monthly_expenses=qp_financial_monthly_expenses, qp_financial_other_income=qp_financial_other_income)
        
    return {
        "supplier": supplier.as_dict()
    }
    
def  set_financial(supplier, qp_financial_assets, qp_financial_liabilities, qp_financial_equity, qp_financial_details_income, qp_financial_monthly_income, qp_financial_monthly_expenses, qp_financial_other_income):
    
    supplier.qp_financial_assets = qp_financial_assets
    supplier.qp_financial_liabilities = qp_financial_liabilities
    supplier.qp_financial_equity = qp_financial_equity
    supplier.qp_financial_details_income = qp_financial_details_income
    supplier.qp_financial_monthly_income = qp_financial_monthly_income
    supplier.qp_financial_monthly_expenses = qp_financial_monthly_expenses
    supplier.qp_financial_other_income = qp_financial_other_income
    