
import frappe

    
def get_shareholder(shareholder_id):
    
    shareholder = frappe.get_doc("qp_SP_ShareHolder", shareholder_id)
    
    return {
        "shareholder": shareholder.as_dict()
    }