
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_bank_accounts
from qp_supplier_front.uses_cases.information.complete import handler as complete
from qp_supplier_front.services.field_validate import handler as validate_field
from qp_supplier_front.services.field_validate import setup_validate_field_list as setup_bank_account_validation
from qp_supplier_front.services.document_utils import set_document, setup_document, setup_validate_field_list, validate_document_expirate

def handler(supplier_id, documents, qp_has_quality_cert, qp_quality_cert_detail, is_estatus_editable):
    
    doctype = "qp_SP_DocumentParty"
    
    
    supplier = get_supplier(supplier_id)
    
    set_document(supplier, documents)
    setup_document(supplier)
    setup_validate_field_list(supplier)
    supplier.qp_has_quality_cert = qp_has_quality_cert
    supplier.qp_quality_cert_detail = qp_quality_cert_detail
    
    validate_document_expirate(supplier)
    
    supplier.save()
    
    if supplier.qp_is_foreigner_supplier:
        
        validate_field(supplier, "international", 0)

    if (is_estatus_editable != "true"):
        
        bank_accounts = get_bank_accounts(supplier, "Bank Account")
        
        setup_bank_account_validation(supplier, bank_accounts, "bank_account", ["bank", "account_type", "bank_account_no"])
        
        supplier.save()
        
        complete(supplier)
    
    return {
        "supplier": supplier
    }