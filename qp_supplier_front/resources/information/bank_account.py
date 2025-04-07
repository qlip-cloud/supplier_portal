import frappe
from qp_supplier_front.uses_cases.information.bank_account.save import handler as save_bank_account   
from qp_supplier_front.uses_cases.information.bank_account.save_complement import handler as save_complement_bank_account   
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.information.bank_account.update import handler as update_bank_account   
from qp_supplier_front.uses_cases.information.bank_account.get import get_bank_account
from qp_supplier_front.services.get_data import get_bank_accounts


@frappe.whitelist()
def save(supplier_id, bank, account_type, bank_account_no, doctype_id = None, swift_number = None, qp_aba_number=None ,iban=None):
    
    method = frappe.local.request.method
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        if method == "POST":
        
            result = save_bank_account(supplier_id, bank, account_type, bank_account_no, swift_number, qp_aba_number, iban)
            
        elif method == "PUT":
            
            result = update_bank_account(supplier_id, doctype_id, bank, account_type, bank_account_no, swift_number, qp_aba_number, iban)
            
        bank_accounts = get_bank_accounts(result.get("supplier"), "Bank Account")
        
        list = frappe.render_template("qp_supplier_front/templates/list/information/bank_accounts.html", {
            "bank_accounts": bank_accounts
        })
        
        result.setdefault("render", {"list": list, "container": "bank_account_list"})    
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear cuenta bancaria: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def save_complement(supplier_id, qp_public_resource_management, qp_public_activity, qp_public_recognition, qp_link_politically_exposed, qp_detail_politically_exposed):
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = save_complement_bank_account(supplier_id, qp_public_resource_management, qp_public_activity, qp_public_recognition, qp_link_politically_exposed, qp_detail_politically_exposed)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar complemento de cuenta bancaria: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def search_bank_account(bank_account_id):
    
    try:
        
        msg = "Los datos han sido buscados correctamente"
        
        result = get_bank_account(bank_account_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al buscados bank_account: {str(error)}"
        
        response(500,  msg)  
        
    
        
