import frappe
import json
from qp_supplier_front.uses_cases.invoice.sync_by_supplier import handler as sync_by_supplier
from qp_supplier_front.services.pagination import get_paginated

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    sync_by_supplier(supplier_id)
    
    key = "sales_invoices"
    
    doctype = "Purchase Invoice"
    
    doctype_detail = "Purchase Invoice Item"
    
    context.supplier_id = supplier_id
    
    context.sales_invoices = get_paginated(0, doctype, supplier_id)
                       
    context.key = key
    
    context.doctype = doctype
    
    context.doctype_detail = doctype_detail