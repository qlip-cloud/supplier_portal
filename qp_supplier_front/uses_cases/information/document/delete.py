

from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import handler as validate_field
from qp_supplier_front.services.document_utils import setup_validate_field_list, validate_document_expirate
import frappe

def handler(supplier_id, setting_id):
    setting_id = setting_id.replace("-"," ")
    supplier = get_supplier(supplier_id)
    
    delete_document(supplier, setting_id)
    
    setup_validate_field_list(supplier)
    
    validate_document_expirate(supplier)
    
    supplier.save()
    
    return {
        "supplier": supplier
    }

def delete_document(supplier, setting_id):
    
    qp_documents = []
        
    for document in supplier.qp_documents:
        
        if document.documento_setting != setting_id:
            
            qp_documents.append(document)
            
        elif document.file_id:
            
            frappe.db.delete("File", {"attached_to_doctype": "Supplier", "attached_to_name": supplier.name, "name": document.file_id})
            
    supplier.qp_documents = qp_documents