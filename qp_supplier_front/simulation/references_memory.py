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


def memory_get_lines_gp(store, doc, force=False):
    """Lineas del payload GP segun el tipo de la factura (en memoria).

    Misma semantica que resources/documenteme/_approbe_base.get_lines_gp:
    - Nota Credito (nvtip_docu == "C"): el tipo (4 o 5) lo resuelve
      memory_resolve_nc_tipo_doc (store). NC tipo 4 no envia productos; NC
      tipo 5 usa el banco de devoluciones de la factura de referencia
      (lineas NC asignadas a recepciones/OC de la referencia). Si la
      devolucion excede el banco queda en error (no se envia), salvo
      force=True.
    - Proveedor servicio (tipo 3): NO se envian productos (vendorInvoiceLine
      vacio); No se valida homologacion ni lineas de la factura.
    - Con recepciones (tipo 1): lineas de las recepciones.
    - Sin recepciones (tipo 2): homogenizar y consolidar contra la OC.
    """
    from qp_supplier_front.uses_cases.documenteme.approve import (
        GP_TIPO_NC_5,
    )
    from qp_supplier_front.uses_cases.documenteme.conversion import is_credit_note

    if is_credit_note(doc.get("nvtip_docu")):
        nc_tipo, nc_error = memory_resolve_nc_tipo_doc(store, doc)
        if nc_error:
            return [], nc_error
        if nc_tipo != GP_TIPO_NC_5:
            return [], ""

        return memory_get_nc_devolution_lines(store, doc, force=force)

    if memory_is_service_supplier(store, doc.get("nvpro_ndoc")):
        return [], ""

    purchase_order = doc.get("nvfac_orde")
    receipt_lines = _memory_gp_lines_from_receipts(store, purchase_order)
    if receipt_lines:
        return receipt_lines, ""

    return _memory_gp_lines_from_invoice(store, doc)


def memory_get_referenced_pi_gp_tipo(store, reference):
    """gp_tipo_factura_doc de la qp_SP_PurchaseInvoice referenciada.

    Espejo de resources/documenteme/_approbe_base.get_referenced_pi_gp_tipo:
    la referencia asignada por el usuario es el numero de factura del
    proveedor (nvfac_nume), no el name de la PI. Se busca por name,
    nvfac_nume o detail.
    """
    if not reference:
        return None
    for field in ("name", "nvfac_nume", "detail"):
        rows = store.query(
            "qp_SP_PurchaseInvoice",
            filters={field: reference},
            fields=["gp_tipo_factura_doc"],
            limit=1,
        )
        if rows:
            return rows[0].get("gp_tipo_factura_doc")
    return None


def memory_resolve_nc_tipo_doc(store, doc):
    """Resuelve el tipoFacturaDoc (4 o 5) de una NC (en memoria).

    Proveedor de servicio: siempre tipo 4 (CxP), sin necesidad de referencia.
    NC tipo 5: usa la referencia asignada por el usuario (qp_ref_invoice); si
    no hay referencia asignada devuelve error (estado SR, no aprobable).
    """
    from qp_supplier_front.uses_cases.documenteme.approve import (
        GP_TIPO_NC,
        resolve_nc_tipo_for_doc,
    )

    if memory_is_service_supplier(store, doc.get("nvpro_ndoc")):
        return GP_TIPO_NC, ""
    reference = (doc or {}).get("qp_ref_invoice") or ""
    if not reference:
        return None, (
            "La nota de credito no tiene una factura de compra de "
            "referencia asignada"
        )
    return resolve_nc_tipo_for_doc(
        doc,
        get_reference_fn=lambda d: (d or {}).get("qp_ref_invoice") or "",
        get_referenced_tipo_fn=lambda ref: memory_get_referenced_pi_gp_tipo(
            store, ref),
    )


def memory_get_referenced_pi(store, reference):
    """qp_SP_PurchaseInvoice referenciada (name, purchase_order_id, tipo)."""
    if not reference:
        return None
    for field in ("name", "nvfac_nume", "detail"):
        rows = store.query(
            "qp_SP_PurchaseInvoice",
            filters={field: reference},
            fields=["name", "purchase_order_id", "gp_tipo_factura_doc"],
            limit=1,
        )
        if rows:
            return rows[0]
    return None


def memory_get_devolution_bank(store, reference, pi):
    """Banco de lineas de la referencia en memoria (recepcion u OC)."""
    from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
        build_po_bank,
        build_receipt_bank,
    )
    from qp_supplier_front.uses_cases.documenteme.approve import (
        GP_TIPO_ENVIO,
    )

    gp_tipo = int((pi or {}).get("gp_tipo_factura_doc") or 0)
    purchase_order = (pi or {}).get("purchase_order_id") or ""

    if gp_tipo == GP_TIPO_ENVIO:
        receipts = store.query(
            "qp_SP_PurchaseReceipt",
            filters={"qp_invoice": reference},
            fields=["name", "qp_supplier_oc"],
        )
        oc_by_receipt = {
            row.get("name"): row.get("qp_supplier_oc") or ""
            for row in receipts
        }
        if receipts:
            items = store.query(
                "qp_SP_PurchaseReceiptItem",
                filters={"parent": ["in", list(oc_by_receipt)],
                         "parenttype": "Purchase Receipt"},
                fields=["parent", "item_code", "qty", "idx", "uom"],
                order_by="parent, idx",
            )
            bank = build_receipt_bank([
                dict(
                    item,
                    receiving_no=item.get("parent") or "",
                    order_no=oc_by_receipt.get(item.get("parent")) or "",
                )
                for item in items
            ])
        else:
            bank = []
    else:
        items = store.query(
            "qp_SP_PurchaseOrderItem",
            filters={"parent": purchase_order,
                     "parenttype": "Purchase Order"},
            fields=["item_code", "qty", "idx", "uom"],
            order_by="idx",
        )
        bank = build_po_bank(items, order_no=purchase_order)

    return bank, memory_get_consumed_devolutions(store, pi)


def memory_get_consumed_devolutions(store, pi):
    """Filas qp_SP_Devolution de la referencia en memoria."""
    if not pi:
        return []
    return store.query(
        "qp_SP_Devolution",
        filters={"reference_invoice": pi.get("name")},
        fields=["item_code", "qty", "receiving_no", "order_no"],
    )


def memory_get_reference_confirmation_id(store, pi):
    """confirmation_id de la qp_SP_PurchaseInvoiceBC de la referencia."""
    if not pi:
        return ""
    name = (pi or {}).get("name") if isinstance(pi, dict) else pi
    if not name:
        return ""
    rows = store.query(
        "qp_SP_PurchaseInvoiceBC",
        filters={"purchase_invoice": name},
        fields=["confirmation_id"],
        limit=1,
    )
    return (rows[0].get("confirmation_id") or "") if rows else ""


def memory_get_nc_devolution_lines(store, doc, force=False):
    """Lineas del payload GP de una NC tipo 5 (memoria) con banco devolution.

    Asigna las lineas de la NC a las lineas de la referencia (recepcion u OC)
    y anota doc["_gp_nc_devolution"] = (reference, pi, assigned) para que la
    persistencia en memoria registre el consumo. Si la devolucion excede el
    banco queda en error (no se envia) salvo force=True.

    Referencia tipo 2: se envia como tipo 1 usando el confirmation_id de la
    qp_SP_PurchaseInvoiceBC de la referencia como numero de recepcion.
    """
    from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
        allocate_devolution,
        apply_consumed,
        excess_message,
    )
    from qp_supplier_front.uses_cases.documenteme.approve import (
        GP_TIPO_ENVIO,
    )

    reference = (doc or {}).get("qp_ref_invoice") or ""
    pi = memory_get_referenced_pi(store, reference)
    if not reference or not pi:
        return [], (
            "No se pudo obtener la factura de compra referenciada por la "
            "nota credito"
        )

    ref_is_tipo1 = (
        int((pi or {}).get("gp_tipo_factura_doc") or 0) == GP_TIPO_ENVIO
    )
    ref_confirmation = (
        "" if ref_is_tipo1
        else memory_get_reference_confirmation_id(store, pi)
    )
    if not ref_is_tipo1 and not ref_confirmation:
        return [], (
            "La factura de compra referenciada por la nota credito no ha sido "
            "confirmada"
        )

    product_lines, line_error = _memory_gp_lines_from_invoice(store, doc)
    if line_error:
        return [], line_error

    bank, consumed = memory_get_devolution_bank(store, reference, pi)
    available = apply_consumed(bank, consumed)
    assigned, excess = allocate_devolution(product_lines, available)

    if excess and not force:
        return [], excess_message(excess)

    by_item = {}
    for line in (product_lines or []):
        by_item.setdefault(line.get("item_code"), line)

    payload_lines = []
    for line in (assigned or []):
        source = by_item.get(line.get("item_code")) or {}
        receiving_no = line.get("receiving_no") or ""
        if not ref_is_tipo1 and not receiving_no and ref_confirmation:
            receiving_no = ref_confirmation
        payload_lines.append({
            "item_code": line.get("item_code"),
            "qty": line.get("qty") or 0,
            "rate": source.get("rate") or 0,
            # noLineaRecepcion: idx de la linea de la OC/recepcion de la
            # referencia asignada.
            "idx": line.get("idx") or source.get("idx") or 0,
            "uom": source.get("uom") or "UN",
            "receiving_no": receiving_no,
            "order_no": line.get("order_no") or "",
        })

    doc["_gp_nc_devolution"] = (reference, pi, assigned)
    return payload_lines, ""


def memory_get_nc_devolution_excess(store, doc):
    """Pre-validacion del banco de la NC tipo 5 (exceso, no confirmacion)."""
    from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
        allocate_devolution,
        apply_consumed,
        excess_message,
    )

    reference = (doc or {}).get("qp_ref_invoice") or ""
    pi = memory_get_referenced_pi(store, reference)
    if not reference or not pi:
        return ""
    product_lines, line_error = _memory_gp_lines_from_invoice(store, doc)
    if line_error:
        return ""
    bank, consumed = memory_get_devolution_bank(store, reference, pi)
    available = apply_consumed(bank, consumed)
    _, excess = allocate_devolution(product_lines, available)
    return excess_message(excess)


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