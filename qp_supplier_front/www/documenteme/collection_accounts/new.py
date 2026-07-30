import frappe
from collections import defaultdict

from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission


def _get_filters(supplier_id):
    if supplier_id:
        return {"supplier_id": supplier_id}

    return {}


def _get_purchase_orders():
    orders = frappe.get_list(
        "Purchase Order",
        fields=["name", "qp_order_id", "qp_create_date", "grand_total", "currency", "supplier"],
        order_by="qp_create_date desc",
    )

    invoiced = frappe.get_list(
        "qp_SP_PurchaseInvoice",
        fields=["name", "purchase_order_id", "total", "supplier"],
    )
    available_by_order = defaultdict(float)
    for invoice in invoiced:
        if invoice.purchase_order_id:
            available_by_order[invoice.purchase_order_id] += float(invoice.total or 0)
        if invoice.name=="ABC305:900245803":
            print("Invoice ABC305:900245803 found with purchase_order_id:", invoice.purchase_order_id)



    for order in orders:
        total_value = float(order.grand_total or 0)
        used_value = available_by_order.get(order.name, 0)
        order.available_value = max(total_value - used_value, 0)

    return orders

def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    context.collection_accounts = frappe.get_list(
        "qp_SP_CollectionAccounts",
        filters=_get_filters(supplier_id),
        fields=[
            "name",
            "supplier_id",
            "supplier",
            "purchase_order",
            "total_due",
            "amount_payable",
            "available_amount"
            ]
    )

    context.purchase_orders = _get_purchase_orders()
    context.show_result = True

    context.has_recent_news = has_recent_news()
    
    
    