from frappe.utils import add_to_date # type: ignore
from qp_supplier_front.services.field_validate import add_field_validations
import frappe
from datetime import datetime

def setup_validate_field_list(supplier):
    
    valid_code = "document"
    
    count = 0
    
    for qp_document in supplier.qp_documents:
        
        
        if qp_document.file and qp_document.is_valid:
            
            count += 1
            
    add_field_validations(supplier,valid_code, count)
    
    
def  set_document(supplier, documents):
    
    for key, document in documents.items():
        
        if document["file"]:
            
            setting_id = key.replace("-", " ")
            
            document_setting = frappe.get_doc("qp_SP_DocumentSetting", setting_id)
        
            validity = add_to_date(datetime.now(), days=document_setting.expire_day)
            
            supplier.append("qp_documents", {
                "documento_setting": setting_id,
                "validity": validity,
                "is_valid": True,
                "file": document["file"],
                "file_id": document["file_id"]
            })
        
def validate_document_expirate(supplier):
    
    qp_has_document_expired = any(document for document in supplier.qp_documents if document.is_valid == False)
    
    supplier.qp_has_document_expired = qp_has_document_expired
    
def setup_document(supplier):
    
    documents = {}
    
    for document in supplier.qp_documents:
        
        if document.file:
            
            if not document.documento_setting in documents:
                
                documents[document.documento_setting] = document
            else:
                
                if document.is_valid and document.creation > documents[document.documento_setting].creation:
                    
                    documents[document.documento_setting] = document
                
    supplier.qp_documents = [document for document in documents.values()]