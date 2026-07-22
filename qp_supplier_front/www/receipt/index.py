import frappe
import json
from qp_supplier_front.services.pagination import get_paginated, get_paginated_filtered
from qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier import sync_by_supplier, sync_all
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

        frappe.log_error(message=frappe.get_traceback(), title="Error sync payment receipts: {} ({})".format(supplier_id, flow))

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    key = "receipts"

    doctype = "qp_SP_PaymentReceipt"

    doctype_detail = "qp_SP_PaymentReceiptItem"

    context.supplier_id = supplier_id

    order_by = "qp_posting_date"

    if flow == "BC":
        context.receipts = get_paginated_filtered(
            0, doctype, order_by,
            filters={"qp_sync_flow": "BC"}
        )
    else:
        context.receipts = get_paginated(0, doctype, supplier_id, order_by)

    context.key = key

    context.doctype = doctype

    context.doctype_detail = doctype_detail

    context.show_result = True

    context.order_by = order_by

    context.date_key = "qp_posting_date"

    context.has_recent_news = has_recent_news()

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
