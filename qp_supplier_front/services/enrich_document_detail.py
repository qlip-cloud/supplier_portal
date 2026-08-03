def enrich_document_detail(document):
    document["factura_interna"] = ""
    purchase_order_number = document.get("nvfac_orde") or ""

    document["ordenes_compra"] = []
    document["recepciones"] = []
    document["productos_orden_compra"] = []
    document["productos_recepcion"] = []

    if purchase_order_number:
        _enrich_purchase_orders(document, purchase_order_number)
        _enrich_payment_receipts(document, purchase_order_number)
        _update_status_if_fully_paid(document)


def _enrich_purchase_orders(document, purchase_order_number):
    import frappe

    if not frappe.db.exists("Purchase Order", purchase_order_number):
        return

    items = frappe.get_all(
        "Purchase Order Item",
        filters={
            "parent": purchase_order_number,
            "parenttype": "Purchase Order",
        },
        fields=["item_code", "uom", "qty", "rate", "amount"]
    )

    document["ordenes_compra"] = [purchase_order_number]
    document["productos_orden_compra"] = build_po_products(items)


def build_po_products(items):
    products = []
    for item in items:
        products.append({
            "codigo": item.get("item_code"),
            "udm": item.get("uom"),
            "cantidad": item.get("qty"),
            "valor_unitario": item.get("rate"),
            "valor_total": item.get("amount"),
        })
    return products


def _enrich_payment_receipts(document, purchase_order_number):
    import frappe

    child_items = frappe.get_all(
        "qp_SP_PaymentReceiptItem",
        filters={
            "qp_document_no_factura": purchase_order_number,
        },
        fields=["parent", "qp_amount"]
    )

    if not child_items:
        document["recepciones"] = []
        document["productos_recepcion"] = []
        return

    applied_by_parent = sum_amounts_by_parent(child_items)

    parent_names = list(applied_by_parent.keys())

    payment_receipts = frappe.get_all(
        "qp_SP_PaymentReceipt",
        filters={
            "name": ["in", parent_names],
        },
        fields=["name", "qp_receipt_id", "qp_posting_date", "qp_description"]
    )

    document["recepciones"] = [receipt.get("qp_receipt_id") for receipt in payment_receipts]
    document["productos_recepcion"] = build_receipt_products(payment_receipts, applied_by_parent)


def sum_amounts_by_parent(child_items):
    applied_by_parent = {}
    for item in child_items:
        parent = item.get("parent")
        amount = item.get("qp_amount") or 0
        applied_by_parent[parent] = applied_by_parent.get(parent, 0) + amount
    return applied_by_parent


def build_receipt_products(payment_receipts, applied_by_parent):
    products = []
    for receipt in payment_receipts:
        applied_amount = applied_by_parent.get(receipt.get("name"), 0)
        products.append({
            "codigo": receipt.get("qp_receipt_id"),
            "udm": "",
            "cantidad": 1,
            "valor_unitario": applied_amount,
            "valor_total": applied_amount,
        })
    return products


def _update_status_if_fully_paid(document):
    import frappe

    total_receipt_amount = sum(
        product["valor_total"]
        for product in document["productos_recepcion"]
    )

    document_total = document.get("nvfac_totp") or 0

    if total_receipt_amount >= document_total and document.get("nvfac_esta") != "A":
        frappe.db.set_value(
            "qp_SP_DocumentDetail",
            document.get("name"),
            "nvfac_esta",
            "A",
        )
        document["nvfac_esta"] = "A"
