import frappe
import json
from qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier import sync_by_supplier
from qp_supplier_front.services.pagination import get_paginated
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission
from qp_supplier_front.services.flow_config import is_flow_configured


def get_context(context):

    context.no_cache = True

    query_params = frappe.request.args

    supplier_id = query_params.get("supplier")

    context.supplier_id = supplier_id

    for flow in ("GP", "BC"):
        if not is_flow_configured(flow):
            continue
        try:
            sync_by_supplier(supplier_id, flow=flow)
        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title="Error sync purchase invoice: {} ({})".format(supplier_id, flow),
            )

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    doctype = "qp_SP_PurchaseInvoice"

    context.order_by = "create_date"

    context.sales_invoices = get_paginated(0, doctype, supplier_id, context.order_by)

    context.key = "sales_invoices"

    context.doctype = doctype

    context.show_result = True

    context.date_key = "create_date"

    context.has_recent_news = has_recent_news()
