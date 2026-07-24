import frappe
from qp_supplier_front.services.pagination import get_paginated_filtered
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission
from qp_supplier_front.services.role_resolver import get_active_role

def get_context(context):
    context.no_cache = True

    query_params = frappe.request.args
    supplier_id = query_params.get("supplier")
    context.supplier_id = supplier_id
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
    context.has_recent_news = has_recent_news()
    context.show_result = True

    user_roles = frappe.get_roles()
    context.active_role = get_active_role(user_roles)
    context.is_documenteme_admin = context.active_role is not None

    key = "documenteme_sales_invoices"
    doctype = "qp_SP_DocumentDetail"
    order_by = "nvfac_fech"
    date_key = "nvfac_fech"

    documents = get_paginated_filtered(0, doctype, order_by, {
        "nvfac_ueve": ["is", "not set"],
    })

    for doc in documents:
        doc["detail_lines"] = frappe.get_all(
            "qp_SP_DetailLine",
            filters={"parent": doc.name, "parenttype": doctype},
            fields=["nvpro_codi", "nvuni_desc", "nvdet_tcan", "nvdet_valo", "nvdet_vdes", "nvdet_stot"]
        )
        doc["attached_files"] = frappe.get_all(
            "qp_SP_DocumentAttach",
            filters={"parent": doc.name, "parenttype": doctype},
            fields=["file_name", "file_type", "file_url", "file_id"]
        )
        doc["non_xml_count"] = len(
            [f for f in doc["attached_files"] if f.get("file_type", "").upper() != "XML"]
        )
        assignee_id = frappe.db.get_value(
            "qp_SP_DocumentSyncLine", doc.get("nvfac_nume"), "assigned_to"
        )
        doc["assigned_to_id"] = assignee_id
        if assignee_id:
            doc["assigned_to_name"] = frappe.db.get_value("User", assignee_id, "full_name") or assignee_id
        else:
            doc["assigned_to_name"] = None
        doc["factura_interna"] = ""
        doc["ordenes_compra"] = []
        doc["recepciones"] = []
        doc["productos_orden_compra"] = []
        doc["productos_recepcion"] = []

    context.documenteme_sales_invoices = documents
    context.key = key
    context.doctype = doctype
    context.order_by = order_by
    context.date_key = date_key
