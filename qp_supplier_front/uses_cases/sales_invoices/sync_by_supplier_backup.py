import frappe
from qp_supplier_front.services.sync_doc import setup_doc
from qp_supplier_front.constant.endpoint import INVOICE_SUPPLIER_ID

def handler(supplier_id):
    
    request_key = "invoices"
    request_key_id = "invoiceId"
    request_list_key = "products"
    request_list_key_id = "itemnmbr"
    doctype = "Purchase Invoice"
    doctype_key = "qp_invoice_id"
    doctype_list_key = "items"
    doctype_list = "Item"
    doctype_list_key_id = "item_code"
    is_validate_items = True
    
    setup_doc(supplier_id, INVOICE_SUPPLIER_ID, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, set_item)
                
def get_doc_base(doctype, doc_new, request_key_id):
    
    doc = frappe.new_doc(doctype)
    
    doc.qp_invoice_id = doc_new.get(request_key_id)
    doc.qp_create_date = doc_new.get("createdate")
    #doc.posting_date = doc_new.get("createdate")
    doc.qp_due_date = doc_new.get("dueDate")
    #doc.due_date = doc_new.get("dueDate")
    doc.qp_subtotal = doc_new.get("subTotal")
    #doc.net_total = doc_new.get("subTotal")
    doc.qp_tax = doc_new.get("tax")
    doc.qp_total = doc_new.get("total")
    doc.qp_currency = doc_new.get("currency")
    #doc.currency = doc_new.get("currency")
    doc.supplier = doc_new.get("vendor")
    doc.qp_status = doc_new.get("status")
    doc.naming_series = "ACC-PINV-.YYYY.-"
    
    return doc
    #doc.due_date = order.get("dueDate")
    
    #doc.qp_status = order.get("status")
     
def set_item(item):
    return {
        "item_code": item.get("itemnmbr"),
        "qp_tax": item.get("taxItem"),
        "qp_qty": item.get("quantity"),
        "qty": 1,
        "qp_unit_cost": item.get("unitCost"),
        "rate": 1,
        "qp_extd_cost": item.get("extdCost"),
        "conversion_factor": 1
    }