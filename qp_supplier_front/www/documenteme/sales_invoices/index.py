import frappe
from qp_supplier_front.services.pagination import get_paginated_filtered
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission
from qp_supplier_front.services.role_resolver import get_active_role
from qp_supplier_front.services.enrich_document_list import enrich_document_list
from qp_supplier_front.services.documenteme_access import (
    get_assigned_sync_lines_filters,
    get_assigned_sync_line_names,
    is_sede_documenteme,
)
from qp_supplier_front.uses_cases.documents.sync_all_whitelist import (
    refresh_documents,
)
from qp_supplier_front.resources.documenteme import runtime


def get_context(context):
    context.no_cache = True

    context.simulation_mode = runtime.is_simulation_enabled()
    context.sync_result = refresh_documents()
    query_params = frappe.request.args
    supplier_id = query_params.get("supplier")
    context.supplier_id = supplier_id
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
    context.has_recent_news = has_recent_news()
    context.show_result = True

    user_roles = frappe.get_roles()
    context.active_role = get_active_role(user_roles)
    context.is_documenteme_admin = context.active_role is not None
    context.is_sede_documenteme = is_sede_documenteme(user_roles)

    data = runtime.resolve()["data"]

    key = "documenteme_sales_invoices"
    doctype = "qp_SP_DocumentDetail"
    order_by = "nvfac_fech"
    date_key = "nvfac_fech"

    filters = {}
    if supplier_id:
        filters["nvpro_ndoc"] = supplier_id

    filters = get_assigned_sync_lines_filters(
        user_roles, frappe.session.user,
        lambda user: get_assigned_sync_line_names(user, data=data),
        filters,
    )

    documents = get_paginated_filtered(0, doctype, order_by, filters, data=data)

    enrich_document_list(documents, doctype, data=data)

    context.documenteme_sales_invoices = documents
    context.key = key
    context.doctype = doctype
    context.order_by = order_by
    context.date_key = date_key
