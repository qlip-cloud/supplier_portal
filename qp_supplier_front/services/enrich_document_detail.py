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
    _enrich_notification(document, data)
    _enrich_conversation(document, data)
    _enrich_factura_interna(document, data)

    if purchase_order_number:
        _enrich_purchase_orders(document, purchase_order_number, references, data)
        _enrich_purchase_receipts(document, purchase_order_number, references, data)
        _enrich_receipt_bank(document, purchase_order_number, references, data)
        _enrich_receipts_detail(document, purchase_order_number, references, data)
        _enrich_price_mismatch(document, references, data)
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
        fields=["confirmation_id", "invoice_id"],
    )
    document["factura_interna"] = (
        confirmation[0].get("confirmation_id") or ""
        if confirmation
        else ""
    )
    document["factura_interna_code"] = (
        confirmation[0].get("invoice_id") or ""
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


def _current_user(data):
    """Usuario activo para las marcas de lectura (real: sesion; memoria: Admin)."""
    if data is not None:
        return "Administrator"

    import frappe
    return getattr(frappe.session, "user", "Administrator")


def _enrich_alerts(document, data=None):
    alerts = _api(data, "get_all")(
        "qp_SP_Alert",
        filters={
            "parent": document.get("name"),
            "status": "Abierta",
        },
        fields=["alert_date", "alert_message", "alert_type"],
        order_by="alert_date desc",
    )

    document["alertas"] = alerts
    document["has_alert"] = bool(alerts)
    document["alert_tooltip"] = build_alert_tooltip(alerts)
    document["alert_severity"] = "ninguno"


def _enrich_notification(document, data=None):
    """Resumen de la notificacion documenteme (event_logs) para tooltip y color.

    - notification_summary: una linea por evento de la secuencia (Ok/En proceso).
    - notification_tooltip: texto compacto del tooltip del icono de alerta.
    - in_progress: True si hay algun evento que aun no termina en Ok (se sigue
      reintentando) o hay alertas abiertas.
    """
    from qp_supplier_front.uses_cases.documenteme.event_logs import (
        build_notification_tooltip,
        notification_summary,
        resolve_sequence,
    )

    events = _api(data, "get_all")(
        "qp_SP_EventLog",
        filters={"parent": document.get("name")},
        fields=["event_code", "status", "response", "attempt_date",
                "error_message"],
    )

    doc_state = document.get("nvfac_esta")
    sequence = resolve_sequence(doc_state, events)
    summary = notification_summary(events, sequence, doc_state)

    document["notification_summary"] = summary
    document["notification_tooltip"] = build_notification_tooltip(summary)
    in_progress = any(
        item.get("status") != "ok" for item in summary
    )

    alerts = document.get("alertas") or []
    urgent = any(
        alert.get("alert_type") == "ErrorUrgente" for alert in alerts
    )

    if urgent:
        document["alert_severity"] = "urgente"
    elif document.get("has_alert") or in_progress:
        document["alert_severity"] = "alerta"
    else:
        document["alert_severity"] = "ninguno"

    tooltip = document.get("notification_tooltip")
    document["alert_tooltip"] = tooltip or build_alert_tooltip(alerts)


def _enrich_conversation(document, data=None):
    """Marca de lectura de la conversacion (comentarios) por usuario actual."""
    user = _current_user(data)
    if data is not None:
        unread = data.timeline.unread_count(document.get("name"), user)
    else:
        from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
            RealTimelineAdapter,
        )
        unread = RealTimelineAdapter().unread_count(document.get("name"), user)
    document["has_unread_conversation"] = unread > 0


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


PRICE_EPSILON = 0.01


def mark_price_mismatches(detail_lines, po_products, homologation_map,
                          epsilon=PRICE_EPSILON):
    """Marca las lineas cuyo precio de factura difiere del de la OC.

    Empareja cada linea de factura con su producto homologado (nvpro_codi ->
    bc_item_code -> item_code de la OC) y compara el valor unitario de la
    factura (nvdet_valo) contra qp_unit_cost de la orden. Como la factura o la
    OC pueden repetir el mismo articulo, las ocurrencias de cada codigo se
    emparejan en orden de aparicion; cada par con precio distinto se marca en
    la linea de factura y en el producto de la OC con el mismo numero de grupo
    (precio_grupo), que el front usa para resaltarlos juntos al pasar el
    cursor. Sin homologacion o sin producto en la OC no se compara.

    Funcion pura: opera sobre las listas recibidas y las muta. Retorna el
    conjunto de codigos con al menos un par en discrepancia.
    """
    for line in detail_lines or []:
        line["precio_difiere"] = False
        line["precio_grupo"] = None
    for product in po_products or []:
        product["precio_difiere"] = False
        product["precio_grupo"] = None

    lines_by_code = _group_indexes_by_code(detail_lines, homologation_map)
    products_by_code = _group_indexes_by_code(po_products, None)

    mismatched = set()
    group = 0
    for code, line_indexes in lines_by_code.items():
        product_indexes = products_by_code.get(code) or []
        for position in range(min(len(line_indexes), len(product_indexes))):
            line = detail_lines[line_indexes[position]]
            product = po_products[product_indexes[position]]
            order_price = product.get("valor_unitario")
            invoice_price = line.get("nvdet_valo")
            if order_price is None or invoice_price is None:
                continue
            if abs(float(invoice_price) - float(order_price)) <= epsilon:
                continue
            group += 1
            line["precio_difiere"] = True
            line["precio_grupo"] = group
            product["precio_difiere"] = True
            product["precio_grupo"] = group
            mismatched.add(code)

    return mismatched


def _group_indexes_by_code(items, homologation_map):
    """Agrupa los indices de las ocurrencias por codigo BC (en orden).

    En las lineas de factura el codigo se resuelve via homologacion
    (nvpro_codi -> bc_item_code); en los productos de la OC el codigo ya es el
    item_code. Los items sin codigo resoluble (sin homologacion) se omiten.
    """
    grouped = {}
    for index, item in enumerate(items or []):
        if homologation_map is None:
            code = item.get("codigo")
        else:
            code = homologation_map.get(item.get("nvpro_codi"))
        if code:
            grouped.setdefault(code, []).append(index)
    return grouped


def _enrich_price_mismatch(document, references=None, data=None):
    """Marca las lineas con precio distinto entre factura y OC.

    Requiere las lineas de la factura (detail_lines) y los productos de la OC
    (productos_orden_compra); si falta alguno no hay comparacion posible. La
    homologacion se resuelve con el adaptador de referencias (real/memoria).
    """
    detail_lines = document.get("detail_lines") or []
    po_products = document.get("productos_orden_compra") or []
    if not detail_lines or not po_products:
        return

    refs = _resolve_references(data, references)
    supplier_by_tax_id = getattr(refs, "supplier_by_tax_id", None)
    homologation_map = getattr(refs, "homologation_map", None)
    if supplier_by_tax_id is None or homologation_map is None:
        return

    supplier = supplier_by_tax_id(document.get("nvpro_ndoc"))
    mark_price_mismatches(
        detail_lines, po_products, homologation_map(supplier)
    )


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

    if data is None:
        from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
            RealTimelineAdapter,
        )
        RealTimelineAdapter().set_state(document.get("name"), "V")
    else:
        data.timeline.set_state(document.get("name"), "V")
    document["nvfac_esta"] = "V"