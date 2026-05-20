import frappe
from qp_supplier_front.uses_cases.supplier.approve import handler as approve_supplier   
from qp_supplier_front.uses_cases.supplier.pre_approved import handler as pre_approved_supplier   
from qp_supplier_front.uses_cases.supplier.reject import handler as reject_supplier   
from qp_supplier_front.uses_cases.supplier.find import handler as find_supplier   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def approve(supplier_id):
    
    try:
        
        msg = "Información aprobada correctamente."
        
        result = approve_supplier(supplier_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al aprobar información: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def pre_approved(supplier_id):
    
    try:
        
        msg = "Información pre aprobada correctamente."
        
        result = pre_approved_supplier(supplier_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al pre aprobar información: {str(error)}"
        
        response(500,  msg)

@frappe.whitelist()
def reject(supplier_id, qp_reject_observation):
    
    try:
        
        msg = "Información rechazada correctamente."
        
        result = reject_supplier(supplier_id, qp_reject_observation)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al rechazando información: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def find(tax_id):
    
    try:
        
        msg = "Busqueda correctamente."
        
        result = find_supplier(tax_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al Buscar información: {str(error)}"
        
        response(500,  msg)