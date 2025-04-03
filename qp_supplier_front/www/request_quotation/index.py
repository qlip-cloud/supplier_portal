import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import INVOICE_ALL

def get_context(context):
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    request_quotations = frappe.db.sql("""
        select 
            request_quotation.* 
        from `tabRequest for Quotation Supplier` as request_quotation_supplier
        inner join  `tabRequest for Quotation` as request_quotation
        on (  request_quotation_supplier.parent = request_quotation.name)
        where request_quotation_supplier.parentfield = 'suppliers' and request_quotation_supplier.supplier = %(supplier_id)s
        """, values={'supplier_id': supplier_id}, as_dict=1)
    
    
    print(request_quotations)
    
    context.request_quotations = request_quotations