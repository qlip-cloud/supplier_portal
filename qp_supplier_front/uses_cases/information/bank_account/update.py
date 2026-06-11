
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_bank_accounts
from qp_supplier_front.services.field_validate import setup_validate_field_list
from qp_supplier_front.services.bank_resolver import resolve_bank_name

def handler(supplier_id, doctype_id, bank, account_type, bank_account_no, swift_number=None, qp_aba_number=None, iban=None, qp_routing_code=None):
    
    doctype = "Bank Account"
    
    valid_code = "bank_account"
    
    supplier = get_supplier(supplier_id)
    
    bank_account = update_bank_account(doctype_id, bank, account_type, bank_account_no, swift_number, qp_aba_number, iban, qp_routing_code)
    
    fields_to_validate = ['bank', 'account_type', 'bank_account_no']
    
    bank_accounts = get_bank_accounts(supplier, doctype)
    
    setup_validate_field_list(supplier, bank_accounts, valid_code, fields_to_validate)
    
    supplier.save()
    
    return {
        "bank_account": bank_account.as_dict(),
        "supplier": supplier
        
    }
    
def update_bank_account(doctype_id, bank, account_type, bank_account_no, swift_number=None, qp_aba_number=None, iban=None, qp_routing_code=None):
    
    doctype = "Bank Account"
    
    bank_account = frappe.get_doc(doctype,doctype_id)

    bank_name = resolve_bank_name(bank, swift_number or "")
    
    bank_doc = setup_bank(bank_name, swift_number, qp_aba_number)
    
    bank_account.bank = bank_name
    
    bank_account.account_type = account_type
    
    bank_account.bank_account_no = bank_account_no

    if iban:
        
        bank_account.qp_iban_number = iban
    
    if qp_routing_code:
        
        bank_account.qp_routing_code = qp_routing_code
    
    bank_account.save(ignore_permissions=True)
    
    return bank_account
    
def setup_bank(bank_name, swift_number, qp_aba_number):
    
    existing_bank = frappe.db.exists("Bank", bank_name)
    
    if not existing_bank:
        
        new_bank = frappe.new_doc("Bank")
        
        new_bank.bank_name = bank_name
        
        update_bank(new_bank , swift_number, qp_aba_number)
            
        new_bank.insert(ignore_permissions=True)
        
        return new_bank
    
    bank_doc = frappe.get_doc("Bank", bank_name)
    
    update_bank(bank_doc , swift_number, qp_aba_number)
    
    bank_doc.save(ignore_permissions=True)
        
    return bank_doc
    
def update_bank(bank , swift_number, qp_aba_number):
    
    if swift_number:
            
        bank.qp_swift_number = swift_number
        
    if qp_aba_number:
        
        bank.qp_aba_number = qp_aba_number
