import frappe
import json
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.information.document.update import handler as update_document   


@frappe.whitelist()
def update(supplier_id, documents, is_estatus_editable):
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        
        documents = json.loads(documents)
        
        result = update_document(supplier_id, documents, is_estatus_editable)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Información Tributaria: {str(error)}"
        
        response(500,  msg)
        
    
        
