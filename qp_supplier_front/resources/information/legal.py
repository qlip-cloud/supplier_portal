import frappe
from qp_supplier_front.uses_cases.information.legal.update import handler as update_legal   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def update(supplier_id, qp_legal_name, qp_legal_id_type, qp_legal_tax_id, qp_legal_place_expedition, qp_legal_date_expedition):
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        result = update_legal(supplier_id, qp_legal_name, qp_legal_id_type, qp_legal_tax_id, qp_legal_place_expedition, qp_legal_date_expedition)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar representante legal: {str(error)}"
        
        response(500,  msg)
        
    
        
