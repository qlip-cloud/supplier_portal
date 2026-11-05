import frappe

from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission


def _get_filters(supplier_id):
    if supplier_id:
        return {"supplier_id": supplier_id}

    return {}


def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    context.is_monitor_view = True
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    context.collection_accounts = frappe.get_list(
        "qp_SP_CollectionAccounts",
        filters=_get_filters(supplier_id),
        fields=[
            "name",
            "creation_date",
            "status",
            "supplier_id",
            "purchase_order",
            "total_due",
            "available_amount",
            "amount_payable",
            "observations",
            "docs",
        ],
        order_by="creation_date desc",
    )

    context.show_result = True

    context.has_recent_news = has_recent_news()
    
    
    