import frappe
from qp_supplier_front.uses_cases.information.bank_account.save import handler as save_bank_account   
from qp_supplier_front.uses_cases.information.bank_account.save_complement import handler as save_complement_bank_account   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def save(supplier_id, bank, account_type, bank_account_no):
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = save_bank_account(supplier_id, bank, account_type, bank_account_no)
        
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
        
    
        
