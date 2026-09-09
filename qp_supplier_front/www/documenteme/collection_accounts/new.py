import frappe

from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission


def _get_purchase_orders(supplier_id):
    if not supplier_id:
        return []

    orders = frappe.get_list(
        "Purchase Order",
        filters={"supplier": supplier_id},
        fields=["name", "qp_order_id", "qp_create_date", "grand_total", "currency", "supplier"],
        order_by="qp_create_date desc",
    )

    if not orders:
        return []

    order_names = tuple(order.get("name") for order in orders)

    used_rows = frappe.db.sql(
        """
        select purchase_order_id, coalesce(sum(total), 0) as used
        from `tabqp_SP_PurchaseInvoice`
        where purchase_order_id in %s
        group by purchase_order_id
        """,
        (order_names,),
        as_dict=True,
    )
    used_by_order = {row.get("purchase_order_id"): float(row.get("used") or 0) for row in used_rows}

    purchase_orders = []
    for order in orders:
        total_value = float(order.get("grand_total") or 0)
        used_value = used_by_order.get(order.get("name"), 0)
        available_value = max(total_value - used_value, 0)
        if available_value <= 0:
            continue
        order["available_value"] = available_value
        purchase_orders.append(order)

    return purchase_orders


def get_context(context):
    
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id

    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)

    context.purchase_orders = _get_purchase_orders(supplier_id)
    context.show_result = True

    context.has_recent_news = has_recent_news()
    
    
    