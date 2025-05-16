
import frappe

    
def get_bank_account(bank_account_id):
    
    bank_account = frappe.get_doc("Bank Account", bank_account_id)

    bank_data = None

    if bank_account.bank:
        bank = frappe.get_doc("Bank", bank_account.bank)
        bank_data = bank.as_dict()
    
    return {
        "bank_account": bank_account.as_dict(), 
        "bank": bank_data
    }