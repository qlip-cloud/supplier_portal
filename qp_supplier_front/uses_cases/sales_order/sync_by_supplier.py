import frappe
from qp_supplier_front.services.sync_doc import setup_doc,get_last_creation, get_result
from qp_supplier_front.util.command import create_doc
from qp_supplier_front.constant.endpoint import ORDER_SUPPLIER_ID, ORDER_SUPPLIER_DATE_RANGE, ORDER_ALL
from datetime import datetime
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.exception.sync import ExceptionAmountMaxLengthNotValid
NOW = str(datetime.now())

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

def handler(supplier_id):
    
    latest_record = get_last_creation(doctype, supplier_id, order_by)
    
    result = get_result(endpoint, supplier_id, latest_record)
    
    setup_doc(result, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, insert_doc, set_item)
@frappe.whitelist()
def handler_all():
    
    result = send_request(ORDER_ALL)
    
    setup_doc(result, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, insert_doc, set_item)
            
def get_doc_base(doc_new, request_key_id, docs, doc_id):
    
    company = frappe.defaults.get_user_default("company")
    
    docs.update({doc_id:(
            doc_id,
            doc_new.get(request_key_id),
            doc_new.get("docDate"),
            doc_new.get("vendor"),
            doc_new.get("prmDate"),
            doc_new.get("docDate"),
            NOW,
            company,
            NOW,
            NOW,
            "Administrator",
            "Administrator"
        )})

def set_item(item, items, doc_id, items_data):
    
    assertAmountMaxLengthValid(item.get("extdCost"),item.get("itemnmbr"), doc_id)

    item_code = item.get("itemnmbr")
    item_id = f"{doc_id}:{item_code}"
    items.update({item_id:(
            item_id,
            item.get("itemnmbr"),
            item.get("qtyOrder"),
            1,
            item.get("unitCost"),
            item.get("unitCost"),
            item.get("extdCost"),
            doc_id,
            "items",
            "Purchase Order",
            item.get("extdCost"),
            items_data.get("item_name", ""),
            NOW,
            NOW,
            "Administrator",
            "Administrator"
        )})

def insert_doc(docs, items):
    
    table = "`tabPurchase Order`"
    
    doc_fiels = "(name, qp_order_id, qp_create_date, supplier, qp_due_date, transaction_date, schedule_date, company, creation, modified, modified_by, owner)"
    
    create_doc(docs, doc_fiels, table)
    
    table_item = "`tabPurchase Order Item`"

    items_fiels = "(name, item_code, qp_qty, qty, qp_unit_cost, rate, qp_extd_cost, parent, parentfield, parenttype, amount, item_name, creation, modified, modified_by, owner)"
    
    create_doc(items, items_fiels, table_item)
    
def assertAmountMaxLengthValid(amount, item_code, order):
    
    if len(amount) > 18:
        
        raise ExceptionAmountMaxLengthNotValid(amount, item_code, order)
