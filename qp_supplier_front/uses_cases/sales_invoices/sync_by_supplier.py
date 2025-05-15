import frappe
from qp_supplier_front.services.sync_doc import setup_doc
from qp_supplier_front.constant.endpoint import INVOICE_SUPPLIER_ID, INVOICE_SUPPLIER_DATE_RANGE
CURRENCY_FORMAT ={
    "DOLARES": "USD",
    "COP": "COP",
    "EUROS": "EUR"
}

@frappe.whitelist() 
def handler(supplier_id):
    
    request_key = "invoices"
    request_key_id = "invoiceId"
    doctype = "qp_SP_PurchaseInvoice"
    doctype_key = "invoice_id"
    request_list_key = None
    request_list_key_id = None
    doctype_list_key = None
    doctype_list = None
    doctype_list_key_id = None
    is_validate_items = False
    order_by = "create_date"
    
    endpoint = {
        "all": INVOICE_SUPPLIER_ID,
        "range": INVOICE_SUPPLIER_DATE_RANGE
    }
    setup_doc(supplier_id, endpoint, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, order_by)
                
def get_doc_base(doctype, doc_new, request_key_id):
    
    doc = frappe.new_doc(doctype)
    
    doc.invoice_id = doc_new.get(request_key_id)
    doc.status = doc_new.get("status")
    doc.create_date = doc_new.get("createdate")
    doc.registration_date = doc_new.get("registrationDate")
    doc.currency = CURRENCY_FORMAT[doc_new.get("currency")]
    doc.subtotal = doc_new.get("subTotal")
    doc.tax = doc_new.get("tax")
    doc.total = doc_new.get("total")
    doc.supplier = doc_new.get("vendor")
    doc.detail = doc_new.get("detail")
        
    return doc