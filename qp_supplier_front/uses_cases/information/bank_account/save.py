
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_bank_accounts
from qp_supplier_front.services.field_validate import setup_validate_field_list

def handler(supplier_id, bank, account_type, bank_account_no, swift_number=None, qp_aba_number=None, iban=None, qp_routing_code=None):
    
    doctype = "Bank Account"
    
    valid_code = "bank_account"
    
    supplier = get_supplier(supplier_id)
    
    bank_account = create_bank_account(supplier, bank, account_type, bank_account_no, swift_number, qp_aba_number, iban, qp_routing_code)
    
    fields_to_validate = ['bank', 'account_type', 'bank_account_no']
    
    bank_accounts = get_bank_accounts(supplier, doctype)
    
    setup_validate_field_list(supplier, bank_accounts, valid_code, fields_to_validate)
    supplier.save()
    return {
        "bank_account": bank_account.as_dict(),
        "supplier": supplier
    }
    
def create_bank_account(supplier, bank, account_type, bank_account_no, swift_number=None, qp_aba_number=None, iban=None, qp_routing_code=None):
    
    doctype = "Bank Account"
    
    bank_name = bank.strip()
    
    existing_bank = frappe.db.exists("Bank", bank_name)

    if not existing_bank:
        
        new_bank = frappe.new_doc("Bank")
        
        new_bank.bank_name = bank_name
        
        if swift_number:
            
            new_bank.qp_swift_number = swift_number
            
        if qp_aba_number:
            
            new_bank.qp_aba_number = qp_aba_number
            
        new_bank.insert(ignore_permissions=True)
        
        frappe.db.commit()

    bank_account = frappe.new_doc(doctype)
    
    bank_account.account_name = f"{supplier.name}:{bank_account_no}"
    bank_account.bank = bank_name
    bank_account.account_type = account_type
    bank_account.bank_account_no = bank_account_no
    bank_account.party_type = supplier.doctype
    bank_account.party = supplier.name

    if iban:
        bank_account.qp_iban_number = iban

    if qp_routing_code:
        bank_account.qp_routing_code = qp_routing_code
    
    if not get_bank_accounts(supplier, doctype):
        
        bank_account.is_default = 1
    
    bank_account.insert()
    
    return bank_account
    
         
