import frappe
from datetime import datetime
from qp_supplier_front.util.command import create_doc
from qp_supplier_front.services.sync_doc import setup_doc
from qp_supplier_front.constant.endpoint import INVOICE_SUPPLIER_ID, INVOICE_SUPPLIER_DATE_RANGE
CURRENCY_FORMAT ={
    "DOLARES": "USD",
    "COP": "COP",
    "EUROS": "EUR"
}
NOW = str(datetime.now())

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
    setup_doc(supplier_id, endpoint, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, order_by, insert_doc)

                

def get_doc_base(doc_new, request_key_id, docs):
        
    docs.update({doc_new.get(request_key_id):(
            doc_new.get(request_key_id),
            doc_new.get(request_key_id),
            doc_new.get("status"),
            doc_new.get("createdate"),
            doc_new.get("registrationDate"),
            doc_new.get("currency"),
            doc_new.get("subTotal"),
            doc_new.get("tax"),
            doc_new.get("total"),
            doc_new.get("vendor"),
            doc_new.get("detail"),
            NOW,
            NOW,
            "Administrator",
            "Administrator"
        )})
    
def insert_doc(docs, items = None):
    
    table = "`tabqp_SP_PurchaseInvoice`"
    
    doc_fiels = "(name, invoice_id, status, create_date, registration_date, currency, subtotal, tax, total, supplier, detail, creation, modified, modified_by, owner)"
    
    create_doc(docs, doc_fiels, table)