
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import setup_validate_field_list
from qp_supplier_front.uses_cases.information.complete import handler as complete
from qp_supplier_front.services.field_validate import handler as validate_field
from frappe.utils import add_to_date # type: ignore
from datetime import datetime

def handler(supplier_id, documents, is_estatus_editable):
    
    doctype = "qp_SP_DocumentParty"
    
    valid_code = "document"
    
    supplier = get_supplier(supplier_id)
    
    set_document(supplier, documents)
    
    fields_to_validate = ['file', "is_valid"]

    setup_validate_field_list(supplier, supplier.qp_documents, valid_code, fields_to_validate)
    
    validate_document_expirate(supplier)
    
    supplier.save()
    
    if supplier.qp_is_foreigner_supplier:
        
        validate_field(supplier, "international", 0)

    if (is_estatus_editable != "true"):
        
        complete(supplier)
    
    return {
        "supplier": supplier
    }
    
def  set_document(supplier, documents):
    
    for key, document in documents.items():
        
        setting_id = key.replace("-", " ")
        
        document_setting = frappe.get_doc("qp_SP_DocumentSetting", setting_id)
    
        validity = add_to_date(datetime.now(), days=document_setting.expire_day)
        
        supplier.append("qp_documents", {
            "documento_setting": setting_id,
            "validity": validity,
            "is_valid": True,
            "file": document["file"]
        })
        
def validate_document_expirate(supplier):
    
    qp_has_document_expired = any(document for document in supplier.qp_documents if document.is_valid == False)
    
    supplier.qp_has_document_expired = qp_has_document_expired