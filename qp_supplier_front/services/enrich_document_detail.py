def enrich_document_detail(document):
    document["factura_interna"] = ""
    purchase_order_number = document.get("nvfac_orde") or ""

    document["ordenes_compra"] = []
    document["recepciones"] = []
    document["productos_orden_compra"] = []
    document["productos_recepcion"] = []

    _enrich_alerts(document)

    if purchase_order_number:
        _enrich_purchase_orders(document, purchase_order_number)
        _enrich_purchase_receipts(document, purchase_order_number)
        _update_status_if_fully_paid(document)


def build_alert_tooltip(alerts):
    if not alerts:
        return None
    lines = ["Alertas:"]
    for alert in alerts:
        date = str(alert.get("alert_date") or "")[:16]
        message = alert.get("alert_message") or ""
        lines.append("- [{}] {}".format(date, message))
    return "\n".join(lines)


def _enrich_alerts(document):
    import frappe

    alerts = frappe.get_all(
        "qp_SP_Alert",
        filters={
            "parent": document.get("name"),
            "parenttype": "qp_SP_DocumentDetail",
            "status": "Abierta",
        },
        fields=["alert_date", "alert_message"],
        order_by="alert_date desc",
    )

    document["alertas"] = alerts
    document["has_alert"] = bool(alerts)
    document["alert_tooltip"] = build_alert_tooltip(alerts)


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
        fields=["item_code", "uom", "qty", "qp_unit_cost", "qp_extd_cost"]
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
            "valor_unitario": item.get("qp_unit_cost"),
            "valor_total": item.get("qp_extd_cost"),
        })
    return products


def _enrich_purchase_receipts(document, purchase_order_number):
    import frappe

    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order_number},
        fields=["name", "supplier_delivery_note", "posting_date", "total"],
    )

    receipt_names = [
        receipt.get("name")
        for receipt in receipts
    ]

    document["recepciones"] = [
        receipt.get("supplier_delivery_note") or receipt.get("name")
        for receipt in receipts
    ]

    items = frappe.get_all(
        "Purchase Receipt Item",
        filters={
            "parent": ["in", receipt_names],
            "parenttype": "Purchase Receipt",
        },
        fields=["item_code", "uom", "qty", "rate", "amount"],
        order_by="parent, idx",
    )
    document["productos_recepcion"] = build_receipt_products(items)


def build_receipt_products(items):
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


def _update_status_if_fully_paid(document):
    import frappe

    total_receipt_amount = sum(
        product["valor_total"]
        for product in document["productos_recepcion"]
    )

    document_total = document.get("nvfac_totp") or 0

    if (total_receipt_amount == document_total
            and document.get("nvfac_esta") not in ("A", "R", "V", "BCC", "PA", "PR")):
        frappe.db.set_value(
            "qp_SP_DocumentDetail",
            document.get("name"),
            "nvfac_esta",
            "V",
        )
        document["nvfac_esta"] = "V"
