
import frappe

    
def get_bank_account(bank_account_id):
    
    bank_account = frappe.get_doc("Bank Account", bank_account_id)
    
    return {
        "bank_account": bank_account.as_dict()
    }