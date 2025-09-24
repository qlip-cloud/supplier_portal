
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_bank_accounts
from qp_supplier_front.services.get_is_estatus_editable import handler as get_is_estatus_editable
from qp_supplier_front.services.field_validate import setup_validate_field_list
    
def handler(supplier_id, bank_account_id):
    
    supplier = get_supplier(supplier_id)
    
    assert_supplier_status_editable(supplier)
        
    frappe.db.delete("Bank Account", {"name": bank_account_id, "party_type": "Supplier", "party": supplier_id})
    
    bank_accounts = get_bank_accounts(supplier, "Bank Account")
    
    valid_code = "bank_account"
    
    fields_to_validate = ['bank', 'account_type', 'bank_account_no']
    
    setup_validate_field_list(supplier, bank_accounts, valid_code, fields_to_validate)
    
    supplier.save()
    
    return {
        "supplier": supplier,
        "bank_accounts": bank_accounts
    }
    
def assert_supplier_status_editable(supplier):
    
    if not get_is_estatus_editable(supplier):
        
        frappe.throw("Esta información no puede ser editada")