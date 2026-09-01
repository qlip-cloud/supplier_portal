# -*- coding: utf-8 -*-
"""
enrich_document_detail.py
=========================
Service para enriquecer el DETALLE de un documento documenteme con alertas,
factura interna (confirmation_id de BC), ordenes de compra y recepciones.

Los datos de referencia (Purchase Order / Purchase Receipt) se leen a traves
de un adaptador inyectable (references): en modo simulador es
MemoryReferenceSource (store en memoria); en modo real, por defecto, se usa
RealReferenceSource (frappe). El facade (data) expone .references, de modo
que la propia vista no cambia: con data presente usa el adaptador de memoria,
sin data usa el real.
"""


def enrich_document_detail(document, data=None, references=None):
    """Enriquece el detalle de un documento con referencias inyectadas.

    - data: facade de datos (None en modo real; en memoria en modo simulador).
    - references: adaptador de referencias de compras (Purchase Order /
      Purchase Receipt). Si es None se resuelve desde data.references o, sin
      data, se usa la implementacion real (frappe).
    """
    document["factura_interna"] = ""
    purchase_order_number = document.get("nvfac_orde") or ""

    document["ordenes_compra"] = []
    document["recepciones"] = []
    document["productos_orden_compra"] = []
    document["productos_recepcion"] = []
    document["banco_recepciones"] = []
    document["recepciones_detalle"] = []
    document["hide_unselected_recibos"] = False

    _enrich_alerts(document, data)
    _enrich_factura_interna(document, data)

    if purchase_order_number:
        _enrich_purchase_orders(document, purchase_order_number, references, data)
        _enrich_purchase_receipts(document, purchase_order_number, references, data)
        _enrich_receipt_bank(document, purchase_order_number, references, data)
        _enrich_receipts_detail(document, purchase_order_number, references, data)
        _update_status_if_fully_paid(document, data, references=references)


def _resolve_references(data, references):
    """Adaptador de referencias: inyectado, o data.references, o real por defecto."""
    if references is not None:
        return references
    if data is not None:
        refs = getattr(data, "references", None)
        if refs is not None:
            return refs
    from qp_supplier_front.infrastructure.adapters.reference_source import (
        RealReferenceSource,
    )
    return RealReferenceSource()


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


def _enrich_purchase_orders(document, purchase_order_number, references=None,
                            data=None):
    refs = _resolve_references(data, references)
    if not refs.po_exists(purchase_order_number):
        return

    items = refs.po_items(purchase_order_number)

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


def _enrich_purchase_receipts(document, purchase_order_number, references=None,
                              data=None):
    refs = _resolve_references(data, references)
    # Solo los recibos asignados/procesados con ESTA factura (qp_invoice ==
    # nvfac_nume); el resto de la OC que no forma parte de la factura no se
    # muestra.
    receipts = refs.receipts_for(
        purchase_order_number,
        qp_invoice=document.get("nvfac_nume"),
    )

    receipt_names = [
        receipt.get("name")
        for receipt in receipts
    ]

    document["recepciones"] = [
        receipt.get("supplier_delivery_note") or receipt.get("name")
        for receipt in receipts
    ]

    items = refs.receipt_items_for(receipt_names)
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


DEFINITIVE_VIEW_STATES = ("BCC", "PA", "PR", "A", "R")


def _enrich_receipt_bank(document, purchase_order_number, references=None,
                         data=None):
    """Banco de recepciones visible para la seleccion manual de la factura.

    - Estado no definitivo: se listan los recibos reclamables (no reclamados
      + los reclamados por esta factura) con checkbox.
    - Estado definitivo: solo se muestran los recibos reclamados por la
      factura, sin checkbox (hide_unselected_recibos = True oculta los no
      seleccionados).
    """
    refs = _resolve_references(data, references)
    invoice_number = document.get("nvfac_nume")
    definitive = document.get("nvfac_esta") in DEFINITIVE_VIEW_STATES
    document["hide_unselected_recibos"] = definitive

    if definitive:
        claimed = refs.receipts_for(
            purchase_order_number, qp_invoice=invoice_number
        )
        document["banco_recepciones"] = [
            {
                "name": receipt.get("name"),
                "amount": receipt.get("total") or 0,
                "date": receipt.get("posting_date"),
                "claimed_by_me": True,
                "selectable": False,
            }
            for receipt in claimed
        ]
        return

    document["banco_recepciones"] = refs.bank_for_invoice(
        purchase_order_number, invoice_number
    )


def _enrich_receipts_detail(document, purchase_order_number, references=None,
                            data=None):
    """Detalle unificado por recepcion: cabecera (banco) + productos agrupados.

    Construye document['recepciones_detalle'] con una entrada por recibo
    visible (las mismas filas de banco_recepciones), cada una con la etiqueta
    del recibo y la tabla de SUS productos.
    """
    bank = document.get("banco_recepciones") or []
    if not bank:
        document["recepciones_detalle"] = []
        return

    refs = _resolve_references(data, references)
    receipts = refs.receipts_for(purchase_order_number)
    labels = {
        receipt.get("name"):
            receipt.get("supplier_delivery_note") or receipt.get("name")
        for receipt in receipts
    }

    names = [row.get("name") for row in bank]
    items = refs.receipt_items_for(names)
    products = build_receipt_products(items)

    products_by_receipt = {}
    for item, product in zip(items, products):
        products_by_receipt.setdefault(item.get("parent"), []).append(product)

    document["recepciones_detalle"] = [
        {
            "name": row.get("name"),
            "etiqueta": labels.get(row.get("name")) or row.get("name"),
            "fecha": row.get("date"),
            "monto": row.get("amount") or 0,
            "claimed_by_me": row.get("claimed_by_me"),
            "selectable": row.get("selectable", False),
            "productos": products_by_receipt.get(row.get("name"), []),
        }
        for row in bank
    ]


def _update_status_if_fully_paid(document, data=None, references=None):
    """Marca en "V" una factura cubierta por una combinacion exacta de
    recepciones no consumidas (banco). Lee el banco via el adaptador de
    referencias (in-memory en simulacion, frappe en real) y respeta los
    estados definitivos/en proceso."""
    refs = _resolve_references(data, references)

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

    bank = refs.receipt_bank_for(purchase_order_number)

    # Seleccion manual en curso: la factura queda a la espera de que el
    # usuario complete y aplique; el flujo automatico no la promueve a "V".
    if any(
        receipt.get("qp_invoice") == document.get("nvfac_nume")
        for receipt in (bank or [])
    ):
        return

    if solve_receipt_bank(document_total, bank, DEFAULT_EPSILON) is None:
        return

    _api(data, "set_value")(
        "qp_SP_DocumentDetail",
        document.get("name"),
        "nvfac_esta",
        "V",
    )
    document["nvfac_esta"] = "V"