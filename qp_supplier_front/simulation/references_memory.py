# -*- coding: utf-8 -*-
"""
references_memory.py (documenteme simulation)
=============================================
Lectura en memoria de datos de referencia (Purchase Order, Purchase Receipt,
Supplier, sede, usuarios) para el modo simulador. Sin seeds devuelven
defaults (no existen); los seeds de escenario los pueblan.

Solo lectura/consulta; los datos de referencia no son "simulados" en si:
se siembran para que approve/assign/reject tengan input.
"""


def memory_po_exists(store, purchase_order):
    if not purchase_order:
        return False
    return store.exists("qp_SP_PurchaseOrder", purchase_order)


def memory_receipts_total(store, purchase_order):
    """Total de recepciones por OC (None si no hay)."""
    rows = store.query("qp_SP_PurchaseReceipt",
                       filters={"qp_supplier_oc": purchase_order})
    if not rows:
        return None
    return sum(float(row.get("total") or 0) for row in rows)


def memory_get_receipt_bank(store, purchase_order):
    """Banco de recepciones (name, amount, date, qp_invoice) por OC."""
    if not purchase_order:
        return []
    rows = store.query("qp_SP_PurchaseReceipt",
                       filters={"qp_supplier_oc": purchase_order})
    return [
        {
            "name": row.get("name"),
            "amount": row.get("total") or 0,
            "date": row.get("posting_date"),
            "qp_invoice": row.get("qp_invoice"),
        }
        for row in rows
    ]


def memory_get_receipt_bank_for_invoice(store, purchase_order, invoice_number):
    """Banco visible para la seleccion manual de una factura (en memoria).

    Recibos no reclamados + los reclamados por ESTA factura; los reclamados
    por otras facturas se excluyen (no visibles ni seleccionables).
    """
    if not purchase_order or not invoice_number:
        return []
    rows = store.query("qp_SP_PurchaseReceipt",
                       filters={"qp_supplier_oc": purchase_order})
    result = []
    for row in rows:
        owner = row.get("qp_invoice")
        if owner and owner != invoice_number:
            continue
        result.append({
            "name": row.get("name"),
            "amount": row.get("total") or 0,
            "date": row.get("posting_date"),
            "qp_invoice": owner,
            "claimed_by_me": owner == invoice_number,
            "selectable": True,
        })
    return result


def memory_has_claimed_receipts(store, invoice_number):
    if not invoice_number:
        return False
    rows = store.query("qp_SP_PurchaseReceipt",
                       filters={"qp_invoice": invoice_number},
                       fields=["name"], limit=1)
    return bool(rows)


def memory_claimed_invoice_numbers(store):
    values = store.query("qp_SP_PurchaseReceipt",
                         filters={"qp_invoice": ["is", "set"]},
                         pluck="qp_invoice")
    return set(value for value in values if value)


def memory_claim_receipts(store, doc, receipt_names):
    """Vincula recepciones a la factura en memoria (espejo del UPDATE guardado).

    Retorna los nombres que no pudieron reclamarse (ya reclamados por otra
    factura).
    """
    if not receipt_names:
        return []
    invoice_number = doc.get("nvfac_nume")
    if not invoice_number:
        return list(receipt_names)
    failed = []
    for name in receipt_names:
        row = store.get("qp_SP_PurchaseReceipt", name)
        if row and row.get("qp_invoice"):
            failed.append(name)
            continue
        store.set_value("qp_SP_PurchaseReceipt", name,
                        "qp_invoice", invoice_number)
    return failed


def memory_release_receipts(store, doc, receipt_names):
    """Libera recepciones reclamadas por ESTA factura (qp_invoice = None)."""
    if not receipt_names:
        return
    invoice_number = doc.get("nvfac_nume")
    if not invoice_number:
        return
    for name in receipt_names:
        row = store.get("qp_SP_PurchaseReceipt", name)
        if row and row.get("qp_invoice") == invoice_number:
            store.set_value("qp_SP_PurchaseReceipt", name,
                            "qp_invoice", None)


def memory_get_headquarter(store, purchase_order):
    if not purchase_order:
        return ""
    return store.get_value("qp_SP_PurchaseOrder", purchase_order, "qp_headquarter") or ""


def memory_get_supplier_by_tax_id(store, tax_id):
    if not tax_id:
        return None
    names = store.query("qp_SP_Supplier", filters={"tax_id": tax_id},
                        pluck="name", limit=1)
    return names[0] if names else None


def memory_is_service_supplier(store, tax_id):
    """True si el proveedor tiene qp_is_service_supplier=1 (tipo GP 3)."""
    supplier = memory_get_supplier_by_tax_id(store, tax_id)
    if not supplier:
        return False
    return bool(store.get_value(
        "qp_SP_Supplier", supplier, "qp_is_service_supplier"
    ) or False)


def memory_is_service_supplier_doc(store, doc):
    """Version doc del check (el core de aprobacion recibe la factura)."""
    return memory_is_service_supplier(store, (doc or {}).get("nvpro_ndoc"))


def memory_has_receipts(store, purchase_order):
    """True si la OC tiene al menos una recepcion (tipo GP 1)."""
    return bool(memory_get_receipt_bank(store, purchase_order))


def memory_get_po_dates(store, purchase_order):
    """Fechas de cabecera de la OC (transaction_date, schedule_date).

    Retorna (None, None) si la OC no existe o no tiene los campos sembrados.
    """
    if not purchase_order:
        return None, None
    row = store.get("qp_SP_PurchaseOrder", purchase_order) or {}
    return row.get("transaction_date"), row.get("schedule_date")


def memory_get_po_items(store, purchase_order):
    """Items de la OC con idx (noLineaRecepcion) para los productos GP."""
    if not purchase_order:
        return []
    return store.query(
        "qp_SP_PurchaseOrderItem",
        filters={"parent": purchase_order,
                 "parenttype": "Purchase Order"},
        fields=["item_code", "idx", "uom"],
        order_by="idx",
    )


def memory_get_homologation_map(store, supplier):
    """Mapa {supplier_item_code: bc_item_code} activo del proveedor."""
    if not supplier:
        return {}
    rows = store.query(
        "qp_SP_ItemHomologation",
        filters={"supplier": supplier, "active": 1},
        fields=["supplier_item_code", "bc_item_code"],
    )
    return {
        row.get("supplier_item_code"): row.get("bc_item_code")
        for row in rows
        if row.get("supplier_item_code")
    }


def memory_get_invoice_detail_lines(store, doc_name):
    """Lineas de la factura del proveedor (misma forma que el adapter real)."""
    return store.query(
        "qp_SP_DetailLine",
        filters={"parent": doc_name},
        fields=["nvpro_codi", "nvdet_tcan", "nvdet_valo"],
    )


def memory_get_lines_gp(store, doc):
    """Lineas del payload GP segun el tipo de la factura (en memoria).

    Misma semantica que resources/documenteme/_approbe_base.get_lines_gp:
    - Proveedor servicio (tipo 3): siempre homogenizacion.
    - Con recepciones (tipo 1): lineas de las recepciones.
    - Sin recepciones (tipo 2): homogenizar y consolidar contra la OC.
    """
    from qp_supplier_front.uses_cases.documenteme.approve import (
        consolidate_gp_lines,
    )

    if memory_is_service_supplier(store, doc.get("nvpro_ndoc")):
        return _memory_gp_lines_from_invoice(store, doc)

    purchase_order = doc.get("nvfac_orde")
    receipt_lines = _memory_gp_lines_from_receipts(store, purchase_order)
    if receipt_lines:
        return receipt_lines, ""

    return _memory_gp_lines_from_invoice(store, doc)


def _memory_gp_lines_from_receipts(store, purchase_order):
    """Items de las recepciones de una OC (codigo ya BC), espejo real."""
    if not purchase_order:
        return []
    receipts = store.query(
        "qp_SP_PurchaseReceipt",
        filters={"qp_supplier_oc": purchase_order},
        pluck="name",
    )
    if not receipts:
        return []
    items = store.query(
        "qp_SP_PurchaseReceiptItem",
        filters={"parent": ["in", receipts],
                 "parenttype": "Purchase Receipt"},
        fields=["parent", "item_code", "qty", "rate", "idx", "uom"],
        order_by="parent, idx",
    )
    return [
        {
            "item_code": item.get("item_code"),
            "qty": item.get("qty"),
            "rate": item.get("rate"),
            "idx": item.get("idx") or 0,
            "uom": item.get("uom") or "",
            "receiving_no": item.get("parent") or "",
            "order_no": purchase_order,
        }
        for item in items
    ]


def _memory_gp_lines_from_invoice(store, doc):
    """Lineas homogenizadas y consolidadas contra la OC (tipo 2/3)."""
    from qp_supplier_front.uses_cases.documenteme.approve import (
        consolidate_gp_lines,
    )

    supplier = memory_get_supplier_by_tax_id(store, doc.get("nvpro_ndoc"))
    homologation_map = memory_get_homologation_map(store, supplier)
    detail_lines = memory_get_invoice_detail_lines(store, doc.get("name"))
    purchase_order = doc.get("nvfac_orde") or ""
    po_items = memory_get_po_items(store, purchase_order) or None

    lines, missing = consolidate_gp_lines(
        detail_lines,
        homologation_map,
        oc_items=po_items,
        order_no=purchase_order,
    )
    if missing:
        return [], (
            "Faltan homologaciones de producto: {}"
        ).format(", ".join(sorted(set(missing))))
    if not lines:
        return [], "La factura no tiene lineas homologadas para enviar"
    return lines, ""


def memory_resolve_gp_tipo_for_doc(store, doc):
    """Tipo GP del documento en memoria: 3 servicio, 1 recepciones, 2 resto."""
    from qp_supplier_front.uses_cases.documenteme.approve import (
        resolve_gp_tipo,
    )

    return resolve_gp_tipo(
        memory_is_service_supplier(store, doc.get("nvpro_ndoc")),
        memory_has_receipts(store, doc.get("nvfac_orde")),
    )


def memory_get_supplier_auto_reject_rule(store, supplier):
    return store.get_value("qp_SP_Supplier", supplier, "auto_reject")


def memory_sede_exists(store, sede_code):
    if not sede_code:
        return False
    return store.exists("qp_md_headquarter", sede_code)


def memory_user_exists(store, email):
    if not email:
        return False
    return store.exists("qp_User", email) or store.exists("User", email)


def memory_get_rule(store, rule_name):
    """Regla qp_SP_AutoRejectRule por name (misma forma que auto_reject.get_rule)."""
    if not rule_name:
        return None
    row = store.get("qp_SP_AutoRejectRule", rule_name)
    if not row:
        return None
    return {
        "rule_name": row.get("rule_name"),
        "rule_code": row.get("rule_code"),
        "enabled": row.get("enabled", 1),
        "motive": row.get("motive"),
    }


def _memory_supplier_rule(store, doc):
    """Regla de auto-rechazo configurada directamente en el proveedor."""
    supplier = memory_get_supplier_by_tax_id(store, doc.get("nvpro_ndoc"))
    if not supplier:
        return None
    return memory_get_rule(
        store, memory_get_supplier_auto_reject_rule(store, supplier))


def memory_resolve_supplier_rule(store, doc):
    """Regla de auto-rechazo SOLO del proveedor (flujo GP servicio).

    Espejo de _approbe_base.resolve_supplier_rule: para proveedores de
    servicio el default global del MasterSetup NO aplica.
    """
    return _memory_supplier_rule(store, doc)


def memory_resolve_rule(store, doc):
    """Regla activa (proveedor con fallback al default del MasterSetup).

    Espejo de resources/documenteme/auto_reject.resolve_rule sobre el store.
    Para proveedores de servicio (flujo GP) solo aplica la regla del
    proveedor: se ignora el default global del MasterSetup.
    Devuelve None si no hay regla activa (equivale a "no action").
    """
    if memory_is_service_supplier(store, doc.get("nvpro_ndoc")):
        return memory_resolve_supplier_rule(store, doc)

    from qp_supplier_front.simulation.master_setup_source import (
        MemoryMasterSetupSource,
    )
    from qp_supplier_front.uses_cases.documenteme.auto_reject import (
        resolve_auto_reject_config,
    )

    supplier_rule = _memory_supplier_rule(store, doc)

    setup_rule = memory_get_rule(
        store, MemoryMasterSetupSource(store).auto_reject_rule())

    return resolve_auto_reject_config(supplier_rule, setup_rule)