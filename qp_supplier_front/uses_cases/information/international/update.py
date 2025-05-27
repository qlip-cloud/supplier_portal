
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import handler as validate_field
def handler(supplier_id, qp_financial_currency_foreigner, qp_financial_which_currency_foreigner, qp_financial_other_operations, qp_financial_item_foreigner, qp_financial_account_currency_foreigner, qp_financial_item_type, qp_financial_item_number, qp_financial_entity, qp_financial_amount, qp_financial_city, qp_financial_country,qp_financial_currency):
    
    supplier = get_supplier(supplier_id)
    
    set_financial(supplier, qp_financial_currency_foreigner, qp_financial_which_currency_foreigner, qp_financial_other_operations, qp_financial_item_foreigner, qp_financial_account_currency_foreigner, qp_financial_item_type, qp_financial_item_number, qp_financial_entity, qp_financial_amount, qp_financial_city, qp_financial_country,qp_financial_currency)
    
    if qp_financial_currency_foreigner=="NO":
        validate_field(supplier, "international" , 0, None, qp_financial_currency_foreigner, qp_financial_item_foreigner, qp_financial_account_currency_foreigner)
    else:
        validate_field(supplier, "international" , 0, None, qp_financial_currency_foreigner, qp_financial_item_foreigner, qp_financial_account_currency_foreigner, qp_financial_amount, qp_financial_city, qp_financial_country,qp_financial_currency)
        
    return {
        "supplier": supplier.as_dict()
    }
    
def  set_financial(supplier, qp_financial_currency_foreigner, qp_financial_which_currency_foreigner, qp_financial_other_operations, qp_financial_item_foreigner, qp_financial_account_currency_foreigner, qp_financial_item_type, qp_financial_item_number, qp_financial_entity, qp_financial_amount, qp_financial_city, qp_financial_country,qp_financial_currency):
    
    supplier.qp_financial_currency_foreigner = qp_financial_currency_foreigner
    supplier.qp_financial_which_currency_foreigner = qp_financial_which_currency_foreigner
    supplier.qp_financial_other_operations = qp_financial_other_operations
    supplier.qp_financial_item_foreigner = qp_financial_item_foreigner
    supplier.qp_financial_account_currency_foreigner = qp_financial_account_currency_foreigner
    supplier.qp_financial_item_type = qp_financial_item_type
    supplier.qp_financial_item_number = qp_financial_item_number
    supplier.qp_financial_entity = qp_financial_entity
    supplier.qp_financial_amount = qp_financial_amount
    supplier.qp_financial_city = qp_financial_city
    supplier.qp_financial_country = qp_financial_country
    supplier.qp_financial_currency = qp_financial_currency
    