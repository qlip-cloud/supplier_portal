import frappe


def enrich_document_detail(document):
    document["factura_interna"] = ""
    purchase_order_number = document.get("nvfac_orde") or ""

    if purchase_order_number:
        document["ordenes_compra"] = []
        document["recepciones"] = []
        document["productos_orden_compra"] = []
        document["productos_recepcion"] = []

        _enrich_purchase_orders(document, purchase_order_number)
        _enrich_payment_receipts(document, purchase_order_number)
        _update_status_if_fully_paid(document)
    else:
        document["ordenes_compra"] = []
        document["recepciones"] = []
        document["productos_orden_compra"] = []
        document["productos_recepcion"] = []


def _enrich_purchase_orders(document, purchase_order_number):
    if not frappe.db.exists("Purchase Order", purchase_order_number):
        return

    purchase_order = frappe.get_doc("Purchase Order", purchase_order_number)
    document["ordenes_compra"] = [purchase_order.name]

    purchase_order_products = []
    for item in purchase_order.items:
        purchase_order_products.append({
            "codigo": item.item_code,
            "udm": item.uom,
            "cantidad": item.qty,
            "valor_unitario": item.rate,
            "valor_total": item.amount,
        })

    document["productos_orden_compra"] = purchase_order_products


def _enrich_payment_receipts(document, purchase_order_number):
    payment_receipts = frappe.get_all(
        "qp_SP_PaymentReceipt",
        filters={
            "qp_document_no_factura": purchase_order_number,
        },
        fields=["name", "qp_receipt_id", "qp_amount", "qp_posting_date", "qp_description"]
    )

    document["recepciones"] = [receipt.name for receipt in payment_receipts]

    receipt_products = []
    for receipt in payment_receipts:
        receipt_item = {
            "codigo": receipt.qp_receipt_id,
            "udm": "",
            "cantidad": 1,
            "valor_unitario": receipt.qp_amount,
            "valor_total": receipt.qp_amount,
        }
        receipt_products.append(receipt_item)

    document["productos_recepcion"] = receipt_products


def _update_status_if_fully_paid(document):
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
