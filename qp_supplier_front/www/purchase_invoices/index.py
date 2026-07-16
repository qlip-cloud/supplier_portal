import frappe
import json
from qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier import sync_by_supplier, sync_all
from qp_supplier_front.services.pagination import get_paginated, get_paginated_filtered
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    flow = query_params.get("flow", "GP")
    
    context.supplier_id = supplier_id
    context.flow = flow
    
    try:
        if flow == "BC":
            sync_all(flow="BC")
        else:
            sync_by_supplier(supplier_id, flow=flow)

    except Exception as e:

        frappe.log_error(message=frappe.get_traceback(), title=f"Error sync purchase invoice: {supplier_id} ({flow})")

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    doctype = "qp_SP_PurchaseInvoice"

    context.order_by = "create_date"
    context.supplier_id = supplier_id

    if flow == "BC":
        context.sales_invoices = get_paginated_filtered(
            0, doctype, context.order_by,
            filters={"qp_sync_flow": "BC"}
        )
    else:
        context.sales_invoices = get_paginated(0, doctype, supplier_id, context.order_by)

    context.key = "sales_invoices"

    context.doctype = doctype

    context.show_result = True

    context.date_key = "create_date"

    context.has_recent_news = has_recent_news()
    
    
    