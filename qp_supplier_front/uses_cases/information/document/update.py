
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import setup_validate_field_list

def handler(supplier_id, documents):
    doctype = "qp_SP_DocumentParty"
    
    valid_code = "document"
    
    supplier = get_supplier(supplier_id)
    
    set_document(supplier, documents)
    
    fields_to_validate = ['validity', 'value', 'file']

    setup_validate_field_list(supplier, supplier.qp_documents, valid_code, fields_to_validate)
    
    supplier.save()

    return {
        "supplier": supplier
    }
    
def  set_document(supplier, documents):
    
    supplier.qp_documents = []
    
    for key, document in documents.items():
        
        supplier.append("qp_documents", {
            "documento_setting": key,
            "validity": document["validity"],
            "value": document["value"],
            "file": document["file"]
        })