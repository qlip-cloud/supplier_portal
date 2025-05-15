import frappe
from qp_supplier_front.services.sync_doc import setup_doc
from qp_supplier_front.constant.endpoint import PAYMENT_SUPPLIER_ID, PAYMENT_SUPPLIER_DATE_RANGE

def handler(supplier_id):
    
    request_key = "payments"
    request_key_id = "vchrnmbr"
    request_list_key = "reference"
    request_list_key_id = "aptvchnm"
    doctype = "Purchase Receipt"
    doctype_key = "qp_receipt_id"
    doctype_list_key = "qp_references"
    doctype_list = None
    doctype_list_key_id = None
    is_validate_items = False
    order_by = "qp_create_date"
    
    endpoint = {
        "all": PAYMENT_SUPPLIER_ID,
        "range": PAYMENT_SUPPLIER_DATE_RANGE
    }
    
    setup_doc(supplier_id, endpoint, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, order_by, set_item)
                
def get_doc_base(doctype, doc_new, request_key_id):
    
    doc = frappe.new_doc(doctype)
    
    doc.qp_receipt_id = doc_new.get(request_key_id)
    doc.qp_create_date = doc_new.get("dinvodof")
    doc.supplier = doc_new.get("vendor")
    doc.posting_date = doc_new.get("docDate")
    doc.qp_amount = doc_new.get("docamnt")
    doc.base_grand_total = 0
    doc.grand_total = 0
    doc.base_rounded_total = 0
    doc.rounded_total = 0
    
    return doc
     
def set_item(item):
    return {
        "qp_aptovcnm": item.get("aptvchnm"),
        "qp_seq": item.get("seq"),
        "qp_appldamt": item.get("appldamt"),
        "qp_aptodcnm": item.get("aptodcnm")
        
    }