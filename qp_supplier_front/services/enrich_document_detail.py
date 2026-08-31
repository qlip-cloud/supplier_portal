# -*- coding: utf-8 -*-
"""
enrich_document_detail.py
=========================
Service para enriquecer el DETALLE de un documento documenteme con alertas,
factura interna (confirmation_id de BC), ordenes de compra y recepciones.

Acepta un facade de datos (data): en modo simulador lee del store en memoria;
sin data usa frappe real (comportamiento original).
"""


def enrich_document_detail(document, data=None):
    document["factura_interna"] = ""
    purchase_order_number = document.get("nvfac_orde") or ""

    document["ordenes_compra"] = []
    document["recepciones"] = []
    document["productos_orden_compra"] = []
    document["productos_recepcion"] = []

    _enrich_alerts(document, data)
    _enrich_factura_interna(document, data)

    if purchase_order_number:
        _enrich_purchase_orders(document, purchase_order_number, data)
        _enrich_purchase_receipts(document, purchase_order_number, data)
        _update_status_if_fully_paid(document, data)


def _api(data, name):
    """Facade (data) o frappe real. Compatible con data.db.set_value/exists."""
    if data is None:
        import frappe
        if name == "exists":
            return frappe.db.exists
        if name == "set_value":
            return frappe.db.set_value
        return frappe.get_all if name == "get_all" else frappe.db.get_value
    if name in ("get_all", "exists"):
        return getattr(data, name)
    if name == "set_value":
        if hasattr(data, "db"):
            return data.db.set_value
        return data.set_value
    return getattr(data, name)


def _enrich_factura_interna(document, data=None):
    confirmation = _api(data, "get_all")(
        "qp_SP_PurchaseInvoiceBC",
        filters={"purchase_invoice": document.get("name")},
        fields=["confirmation_id"],
    )
    document["factura_interna"] = (
        confirmation[0].get("confirmation_id") or ""
        if confirmation
        else ""
    )


def build_alert_tooltip(alerts):
    if not alerts:
        return None
    lines = ["Alertas:"]
    for alert in alerts:
        date = str(alert.get("alert_date") or "")[:16]
        message = alert.get("alert_message") or ""
        lines.append("- [{}] {}".format(date, message))
    return "\n".join(lines)


def _enrich_alerts(document, data=None):
    alerts = _api(data, "get_all")(
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


def _enrich_purchase_orders(document, purchase_order_number, data=None):
    if not _api(data, "exists")("Purchase Order", purchase_order_number):
        return

    items = _api(data, "get_all")(
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


def _enrich_purchase_receipts(document, purchase_order_number, data=None):
    receipts = _api(data, "get_all")(
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

    items = _api(data, "get_all")(
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


def _update_status_if_fully_paid(document, data=None):
    """Marca en "V" una factura cubierta por una combinacion exacta de
    recepciones no consumidas (banco). Lee el banco via el facade (data) o
    frappe real y respeta los estados definitivos/en proceso."""
    from qp_supplier_front.uses_cases.documenteme.receipt_bank import (
        DEFAULT_EPSILON,
        solve_receipt_bank,
    )

    document_total = document.get("nvfac_stot") or 0
    purchase_order_number = document.get("nvfac_orde")

    if document.get("nvfac_esta") in ("A", "R", "V", "BCC", "PA", "PR"):
        return

    if not purchase_order_number:
        return

    receipts = _api(data, "get_all")(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order_number},
        fields=["name", "total", "posting_date", "qp_invoice"],
    )

    bank = [
        {
            "name": receipt.get("name"),
            "amount": receipt.get("total") or 0,
            "date": receipt.get("posting_date"),
            "qp_invoice": receipt.get("qp_invoice"),
        }
        for receipt in (receipts or [])
    ]

    if solve_receipt_bank(document_total, bank, DEFAULT_EPSILON) is None:
        return

    _api(data, "set_value")(
        "qp_SP_DocumentDetail",
        document.get("name"),
        "nvfac_esta",
        "V",
    )
    document["nvfac_esta"] = "V"
