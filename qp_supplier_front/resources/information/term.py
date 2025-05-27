import frappe
from qp_supplier_front.uses_cases.information.term.accept import handler as accept_term   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def accept(supplier_id, accept_type):
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = accept_term(supplier_id, accept_type)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Información Tributaria: {str(error)}"
        
        response(500,  msg)