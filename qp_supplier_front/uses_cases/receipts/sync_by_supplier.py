import frappe
from qp_supplier_front.services.sync_doc import setup_doc
from qp_supplier_front.constant.endpoint import PAYMENT_SUPPLIER_ID, PAYMENT_SUPPLIER_DATE_RANGE
from qp_supplier_front.util.command import create_doc
from datetime import datetime
NOW = str(datetime.now())

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
    
    setup_doc(supplier_id, endpoint, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, order_by, insert_doc, set_item)
                
       
def get_doc_base(doc_new, request_key_id, docs):
    
    company = frappe.defaults.get_user_default("company")
    
    docs.update({doc_new.get(request_key_id):(
            doc_new.get(request_key_id),
            doc_new.get(request_key_id),
            doc_new.get("dinvodof"),
            doc_new.get("vendor"),
            doc_new.get("dinvodof"),
            doc_new.get("docamnt"),
            0,
            0,
            0,
            0,
            company,
            NOW,
            NOW,
            "Administrator",
            "Administrator"
        )})

def set_item(item, items, doc_id, items_data = None):

    item_code = item.get("aptvchnm")
    items.update({f"{doc_id}:{item_code}":(
            f"{doc_id}:{item_code}",
            item.get("aptvchnm"),
            item.get("seq"),
            item.get("appldamt"),
            item.get("aptodcnm"),
            doc_id,
            "qp_references",
            "Purchase Receipt",
            NOW,
            NOW,
            "Administrator",
            "Administrator"
        )})

def insert_doc(docs, items):
    
    table = "`tabPurchase Receipt`"
    
    doc_fiels = "(name, qp_receipt_id, qp_create_date, supplier, posting_date, qp_amount, base_grand_total, grand_total, base_rounded_total, rounded_total, company, creation, modified, modified_by, owner)"
    
    create_doc(docs, doc_fiels, table)
    
    table_item = "`tabqp_SP_PurchaseReceiptItem`"

    items_fiels = "(name, qp_aptovcnm, qp_seq, qp_appldamt, qp_aptodcnm, parent, parentfield, parenttype, creation, modified, modified_by, owner)"
    
    create_doc(items, items_fiels, table_item)