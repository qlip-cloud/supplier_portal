import frappe
import json
from qp_supplier_front.services.pagination import get_paginated
from qp_supplier_front.uses_cases.receipts.sync_by_supplier import handler as sync_by_supplier

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    sync_by_supplier(supplier_id)
    
    key = "receipts"
    
    doctype = "Purchase Receipt"
    
    doctype_detail = "qp_SP_PurchaseReceiptItem"
    
    context.supplier_id = supplier_id
    
    context.receipts = get_paginated(0, doctype, supplier_id)
                       
    context.key = key
    
    context.doctype = doctype
    
    context.doctype_detail = doctype_detail