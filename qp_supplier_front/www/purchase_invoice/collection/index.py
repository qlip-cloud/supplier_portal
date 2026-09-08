import frappe
from qp_supplier_front.resources.collection_accounts import (
    _collection_invoice_base as base,
)
from qp_supplier_front.resources.collection_accounts import runtime
from qp_supplier_front.services.get_data import get_has_dispatch_permission, has_recent_news
from qp_supplier_front.services.pagination import get_paginated_filtered
from qp_supplier_front.services.role_resolver import get_active_role


def get_context(context):
    context.no_cache = True

    context.simulation_mode = runtime.is_simulation_enabled()

    query_params = frappe.request.args
    supplier_id = query_params.get("supplier")
    context.supplier_id = supplier_id
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
    context.has_recent_news = has_recent_news()
    context.show_result = True

    user_roles = frappe.get_roles()
    context.active_role = get_active_role(user_roles)
    context.is_documenteme_admin = context.active_role is not None

    data = runtime.resolve().get("data")

    key = "purchase_invoice_collection"
    doctype = "qp_SP_PurchaseInvoice"
    order_by = "registration_date"
    date_key = "registration_date"

    filters = {"qp_sync_flow": "COLLECTION"}
    if supplier_id:
        filters["nvpro_ndoc"] = supplier_id

    documents = get_paginated_filtered(0, doctype, order_by, filters, data=data)

    base.attach_notification_info(documents, data=data)

    context.purchase_invoice_collection = documents
    context.key = key
    context.doctype = doctype
    context.order_by = order_by
    context.date_key = date_key