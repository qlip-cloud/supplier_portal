import frappe
from qp_supplier_front.services.sync_doc import setup_doc
from qp_supplier_front.constant.endpoint import ORDER_SUPPLIER_ID, ORDER_SUPPLIER_DATE_RANGE
from datetime import datetime
def handler(supplier_id):
    
    request_key = "orders"
    request_key_id = "orderId"
    request_list_key = "products"
    request_list_key_id = "itemnmbr"
    doctype = "Purchase Order"
    doctype_key = "qp_order_id"
    doctype_list_key = "items"
    doctype_list = "Item"
    doctype_list_key_id = "item_code"
    is_validate_items = True
    order_by = "qp_create_date"
    
    endpoint = {
        "all": ORDER_SUPPLIER_ID,
        "range": ORDER_SUPPLIER_DATE_RANGE
    }
    
    setup_doc(supplier_id, endpoint, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, order_by, set_item)
                
def get_doc_base(doctype, doc_new, request_key_id):
    
    doc = frappe.new_doc(doctype)
    
    doc.qp_order_id = doc_new.get(request_key_id)
    doc.qp_create_date = doc_new.get("docDate")
    doc.supplier = doc_new.get("vendor")
    doc.qp_due_date = doc_new.get("prmDate")
    doc.posting_date = doc_new.get("docDate")
    doc.schedule_date = datetime.now()
    
    return doc
    #doc.due_date = order.get("dueDate")
    
    #doc.qp_status = order.get("status")
    
    
def set_item(item):
    
    return {
        "item_code": item.get("itemnmbr"),
        "qp_qty": item.get("qtyOrder"),
        "qty": 1,
        "qp_unit_cost": item.get("unitCost"),
        "rate": item.get("unitCost"),
        "qp_extd_cost": item.get("extdCost")
        #"conversion_factor": 1
    }
    