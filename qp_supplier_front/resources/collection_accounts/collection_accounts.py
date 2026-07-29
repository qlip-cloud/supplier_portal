import frappe


def _get_current_available_amount(purchase_order_name):
    purchase_order = frappe.db.get_value(
        "Purchase Order",
        purchase_order_name,
        ["name", "supplier", "grand_total", "currency"],
        as_dict=True,
    )

    if not purchase_order:
        frappe.throw("La orden de compra no existe.")

    total_due = float(purchase_order.grand_total or 0)
    already_invoiced = frappe.db.sql(
        """
        select coalesce(sum(total), 0)
        from `tabqp_SP_PurchaseInvoice`
        where purchase_order_id = %s
        """,
        (purchase_order_name,),
    )[0][0] or 0

    available_amount = max(total_due - float(already_invoiced), 0)

    return purchase_order, total_due, available_amount


@frappe.whitelist()
def create_collection_account(purchase_order, amount_to_invoice, observations=None, docs=None):
    purchase_order_doc, total_due, available_amount = _get_current_available_amount(purchase_order)

    amount_to_invoice = float(amount_to_invoice or 0)

    if amount_to_invoice <= 0:
        frappe.throw("El monto a facturar debe ser mayor a cero.")

    if amount_to_invoice > available_amount:
        frappe.throw(
            f"El monto a facturar no puede ser mayor al valor disponible ({frappe.format_value(available_amount, 'Currency', currency=purchase_order_doc.currency or 'COP')})."
        )

    collection_account = frappe.new_doc("qp_SP_CollectionAccounts")
    collection_account.supplier_id = purchase_order_doc.supplier
    collection_account.purchase_order = purchase_order_doc.name
    collection_account.total_due = total_due
    collection_account.available_amount = available_amount
    collection_account.amount_payable = amount_to_invoice
    collection_account.observations = observations
    collection_account.creation_date = frappe.utils.nowdate()

    if docs:
        collection_account.docs = docs

    collection_account.insert(ignore_permissions=True)

    return {
        "name": collection_account.name,
        "available_amount": available_amount,
        "amount_payable": amount_to_invoice,
    }