import frappe
import json
from qp_supplier_front.services.pagination import get_paginated
from qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier import sync_by_supplier
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission
from qp_supplier_front.services.flow_config import is_flow_configured


def get_context(context):

    context.no_cache = True

    query_params = frappe.request.args

    supplier_id = query_params.get("supplier")

    context.supplier_id = supplier_id

    for flow in ("GP", "BC"):
        if not is_flow_configured(flow, domain="receipt"):
            continue
        try:
            sync_by_supplier(supplier_id, flow=flow)

        except Exception as e:

            frappe.log_error(
                message=frappe.get_traceback(),
                title="Error sync payment receipts: {} ({})".format(supplier_id, flow),
            )

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    key = "receipts"

    doctype = "qp_SP_PaymentReceipt"

    doctype_detail = "qp_SP_PaymentReceiptItem"

    context.supplier_id = supplier_id

    order_by = "qp_posting_date"

    context.receipts = get_paginated(0, doctype, supplier_id, order_by)

    context.key = key

    context.doctype = doctype

    context.doctype_detail = doctype_detail

    context.show_result = True

    context.order_by = order_by

    context.date_key = "qp_posting_date"

    context.has_recent_news = has_recent_news()

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
