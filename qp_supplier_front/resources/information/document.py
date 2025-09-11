import frappe
import json
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.information.document.update import handler as update_document
from qp_supplier_front.uses_cases.information.document.delete import handler as delete_document


@frappe.whitelist()
def update(supplier_id, documents, qp_has_quality_cert, qp_quality_cert_detail, is_estatus_editable):

    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        documents = json.loads(documents)

        result = update_document(supplier_id, documents, qp_has_quality_cert, qp_quality_cert_detail, is_estatus_editable)
    
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Información Tributaria: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def delete(supplier_id, setting_id):

    try:
        
        msg = "Los datos han sido eliminados correctamente"
        
        result = delete_document(supplier_id, setting_id)
    
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Información Tributaria: {str(error)}"
        
        response(500,  msg)
        
    
        
