# -*- coding: utf-8 -*-
"""
_approve_base.py (documenteme)
==============================
Cablea el nucleo puro de aprobacion (uses_cases/documenteme/approve) con
implementaciones Frappe. Es el equivalente de _reject_base.py para el
rechazo y sirve a los flujos manual (resources/documenteme/approve.py) y
automatico (resources/documenteme/auto_approve.py).
"""

import frappe
from frappe import parse_json

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_receipt_bank as _adapter_get_receipt_bank,
    get_receipt_total as _adapter_get_receipt_total,
)
from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.documenteme.auto_reject import (
    get_supplier_rule as _get_supplier_rule,
    resolve_rule as _resolve_rule,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.role_resolver import get_active_role
from qp_supplier_front.uses_cases.documenteme.approve import (
    GP_TIPO_ENVIO,
    GP_TIPO_NC,
    GP_TIPO_NC_5,
    approve_documents,
    collect_registrable_violations,
    make_invoice_builder,
    resolve_nc_tipo_for_doc,
)
from qp_supplier_front.uses_cases.documenteme.conversion import is_credit_note

ALLOWED_ROLES = {"Administrador Documenteme", "Administrador Sede Documenteme"}


def _has_permission(user_roles):
    active = get_active_role(user_roles)
    return active in ALLOWED_ROLES


def _make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================================================================
# Callbacks de infraestructura
# =========================================================================
def get_docs(doc_names):
    return frappe.get_all(
        "qp_SP_DocumentDetail",
        filters={"name": ["in", list(doc_names)]},
        fields=[
            "name",
            "nvfac_nume",
            "nvpro_ndoc",
            "nvfac_fech",
            "nvfac_cufe",
            "nvtip_docu",
            "nvfac_fpag",
            "nvfac_orde",
            "nvfac_rece",
            "nvfac_totp",
            "nvfac_esta",
            "nvfac_ueve",
            "nvfac_conv",
            "nvmon_codi",
            "nvfac_stot",
            "nvfac_viva",
            "nvpro_nomb",
            "qp_ref_invoice",
            "qp_ref_date_start",
            "qp_ref_date_end",
        ],
    )


def get_lines(doc):
    """Resuelve las lineas que alimentan el payload BC para una factura.

    Retorna (lines, error):
    - lines: lista de dicts {item_code, qty, rate, idx, receiving_no, order_no}.
    - error: mensaje si la factura no puede generar lineas (vacio si ok).

    Fuente de lineas:
    - Si la OC tiene recepciones: se usan los Purchase Receipt Items, cuyo
      item_code ya es el codigo BC. Aplica a credito (obligatorio) y a contado
      con recepcion.
    - Si no hay recepciones (contado sin recibo, o credito aprobado por el
      usuario en modo forzado): se toman las lineas de la factura del
      proveedor (qp_SP_DetailLine) y se homologa el codigo del proveedor
      (nvpro_codi) al codigo BC (bc_item_code) via la tabla
      qp_SP_ItemHomologation. Si algun codigo no tiene homologacion la
      factura queda en error (se mantiene en "E" con alerta).
    """
    purchase_order = doc.get("nvfac_orde")
    receipt_lines = get_lines_from_receipts(purchase_order)

    if receipt_lines:
        return receipt_lines, ""

    return get_lines_from_invoice(doc)


def get_lines_from_receipts(purchase_order, receipt_names=None):
    """Lineas desde los Purchase Receipt Items de una OC (codigo ya BC).

    Con receipt_names se restringe a SOLO esos recibos (seleccion manual del
    banco); sin el parametro conserva el comportamiento original (todos los
    recibos de la OC).
    """
    if not purchase_order:
        return []
    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order},
        pluck="name",
    )
    if receipt_names is not None:
        wanted = set(receipt_names)
        receipts = [name for name in receipts if name in wanted]
    if not receipts:
        return []
    items = frappe.get_all(
        "Purchase Receipt Item",
        filters={"parent": ["in", receipts], "parenttype": "Purchase Receipt"},
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


def get_lines_from_invoice(doc):
    """Lineas de la factura del proveedor homologadas al codigo BC.

    Resuelve el proveedor por tax_id (nvpro_ndoc), carga el mapa de
    homologacion y las lineas de detalle de la factura. Si falta alguna
    homologacion retorna un error con los codigos pendientes.

    El JSON a BC lleva la informacion que la factura tiene: si el contado
    tiene OC (pero no recibo) se incluye NoPedido (order_no); sin OC/recibo
    van vacios y BC decide.
    """
    from qp_supplier_front.infrastructure.adapters.item_homologation_adapter import (
        get_homologation_map,
        get_invoice_detail_lines,
        resolve_supplier,
    )
    from qp_supplier_front.uses_cases.documenteme.approve import homologate_lines

    supplier = resolve_supplier(doc.get("nvpro_ndoc"))
    homologation_map = get_homologation_map(supplier)
    detail_lines = get_invoice_detail_lines(doc.get("name"))

    lines, missing_codes = homologate_lines(
        detail_lines,
        homologation_map,
        order_no=doc.get("nvfac_orde") or "",
    )

    if missing_codes:
        return [], (
            "Faltan homologaciones de producto: {}"
        ).format(", ".join(sorted(set(missing_codes))))

    if not lines:
        return [], "La factura no tiene lineas homologadas para enviar"

    return lines, ""


def po_exists(purchase_order):
    if not purchase_order:
        return False
    return bool(frappe.db.exists("Purchase Order", purchase_order))


def get_headquarter(purchase_order):
    if not purchase_order:
        return ""
    return frappe.db.get_value("Purchase Order", purchase_order, "qp_headquarter") or ""


def receipts_total(purchase_order):
    """Suma del total de Purchase Receipt por OC (delega en el adapter)."""
    return _adapter_get_receipt_total(purchase_order, frappe_module=frappe)


def receipt_bank(purchase_order):
    """Banco de recepciones (name, amount, date, qp_invoice) por OC."""
    return _adapter_get_receipt_bank(purchase_order, frappe_module=frappe)


def consume_receipts(doc, receipt_names):
    """Marca las recepciones asignadas con qp_invoice = nvfac_nume.

    UPDATE guardado para evitar doble consumo bajo concurrencia: solo se
    consumen recepciones cuyo qp_invoice sigue vacio.
    """
    if not receipt_names:
        return
    invoice_number = doc.get("nvfac_nume")
    if not invoice_number:
        return
    placeholders = ", ".join(["%s"] * len(receipt_names))
    frappe.db.sql(
        "UPDATE `tabPurchase Receipt` SET qp_invoice = %s "
        "WHERE name IN ({}) AND (qp_invoice IS NULL OR qp_invoice = '')".format(
            placeholders
        ),
        [invoice_number] + list(receipt_names),
    )


def get_supplier_by_tax_id(tax_id):
    if not tax_id:
        return None
    suppliers = frappe.get_all(
        "Supplier",
        filters={"tax_id": tax_id},
        pluck="name",
        limit=1,
    )
    if not suppliers:
        return None
    name = suppliers[0]
    if not isinstance(name, str) or not name:
        return None
    return name


def is_service_supplier(tax_id):
    """True si el proveedor de la factura tiene qp_is_service_supplier=1.

    El check manda el tipo GP 3 (CxP) con prioridad absoluta.
    """
    supplier = get_supplier_by_tax_id(tax_id)
    if not supplier:
        return False
    return bool(frappe.db.get_value(
        "Supplier", supplier, "qp_is_service_supplier"
    ))


def is_service_supplier_doc(doc):
    """Version del check para el nucleo puro: recibe el documento completo.

    El core de aprobacion (is_service_supplier_fn) recibe el dict de la
    factura, no el NIT.
    """
    return is_service_supplier((doc or {}).get("nvpro_ndoc"))


def resolve_supplier_rule(doc):
    """Regla de auto-rechazo SOLO del proveedor (sin fallback al MasterSetup).

    Para los proveedores de servicio (flujo GP) el default global de rechazo
    del MasterSetup NO aplica: solo la regla configurada en el Supplier puede
    bloquear la aprobacion automatica.
    """
    return _get_supplier_rule(doc.get("nvpro_ndoc"))


def has_receipts(purchase_order):
    """True si la OC tiene al menos una recepcion (tipo GP 1)."""
    return bool(receipt_bank(purchase_order))


def get_po_dates(purchase_order):
    """Fechas de cabecera de la OC (transaction_date, schedule_date).

    Alimenta fechaRequerida/fechaPrometida de las lineas GP (todas iguales).
    Retorna (None, None) si la OC no existe o no tiene los campos.
    """
    if not purchase_order:
        return None, None
    row = frappe.db.get_value(
        "Purchase Order", purchase_order,
        ["transaction_date", "schedule_date"], as_dict=True,
    ) or {}
    return row.get("transaction_date"), row.get("schedule_date")


def get_po_items_for_gp(purchase_order):
    """Items de la OC con idx (noLineaRecepcion) para los productos GP."""
    if not purchase_order:
        return []
    return frappe.get_all(
        "Purchase Order Item",
        filters={"parent": purchase_order, "parenttype": "Purchase Order"},
        fields=["item_code", "idx", "uom"],
        order_by="idx",
    )


def resolve_gp_tipo_for_doc(doc):
    """Tipo GP del documento: 3 servicio, 1 con recepciones, 2 sin ellas."""
    from qp_supplier_front.uses_cases.documenteme.approve import (
        resolve_gp_tipo,
    )

    return resolve_gp_tipo(
        is_service_supplier(doc.get("nvpro_ndoc")),
        has_receipts(doc.get("nvfac_orde")),
    )


def _get_lines_gp_from_invoice(doc):
    """Lineas GP homogenizadas y consolidadas contra la OC (tipo 2).

    Reusa el nucleo puro consolidate_gp_lines: homogeniza nvpro_codi ->
    bc_item_code, filtra los productos que coinciden con la OC (una OC que
    puede estar parcialmente facturada) y consolida por producto (cantidad y
    monto; idx de la OC).
    """
    from qp_supplier_front.infrastructure.adapters.item_homologation_adapter import (
        get_homologation_map,
        get_invoice_detail_lines,
        resolve_supplier,
    )
    from qp_supplier_front.uses_cases.documenteme.approve import (
        consolidate_gp_lines,
    )

    supplier = resolve_supplier(doc.get("nvpro_ndoc"))
    homologation_map = get_homologation_map(supplier)
    detail_lines = get_invoice_detail_lines(doc.get("name"))
    purchase_order = doc.get("nvfac_orde")
    po_items = get_po_items_for_gp(purchase_order) if purchase_order else None

    lines, missing = consolidate_gp_lines(
        detail_lines,
        homologation_map,
        oc_items=po_items,
        order_no=purchase_order or "",
    )
    if missing:
        return [], (
            "Faltan homologaciones de producto: {}"
        ).format(", ".join(sorted(set(missing))))
    if not lines:
        return [], "La factura no tiene lineas homologadas para enviar"
    return lines, ""


def get_lines_gp(doc, resolve_nc_tipo_fn=None, force=False):
    """Lineas del payload GP segun el tipo de la factura.

    - Nota Credito (nvtip_docu == "C"): el tipo (4 o 5) lo resuelve
      resolve_nc_tipo_fn(doc) -> (4, "") / (5, "") / (None, error). NC tipo 4
      no envia productos (vendorInvoiceLine vacio). NC tipo 5 se carga como el
      tipo 1 con un banco de devoluciones de la factura de referencia: las
      lineas de la NC se asignan a las lineas de recepcion/OC de la referencia
      (order/recibo de esa linea). Si la devolucion excede el banco queda en
      error (no se envia) salvo force=True (aprobacion manual confirmada).
    - Proveedor servicio (tipo 3 CxP): NO se envian productos. La peticion
      va solo con la cabecera (vendorInvoiceLine vacio) y No se valida
      homologacion ni lineas de la factura.
    - Con recepciones (tipo 1): las lineas de las recepciones (comportamiento
      actual de documenteme).
    - Sin recepciones (tipo 2): homogenizar y consolidar contra la OC.
    """
    if is_credit_note(doc.get("nvtip_docu")):
        if resolve_nc_tipo_fn is None:
            return [], ""
        nc_tipo, nc_error = resolve_nc_tipo_fn(doc)
        if nc_error:
            return [], nc_error
        if nc_tipo != GP_TIPO_NC_5:
            return [], ""
        return get_nc_devolution_lines(doc, force=force)

    if is_service_supplier(doc.get("nvpro_ndoc")):
        return [], ""

    purchase_order = doc.get("nvfac_orde")
    receipt_lines = get_lines_from_receipts(purchase_order)
    if receipt_lines:
        return receipt_lines, ""

    return _get_lines_gp_from_invoice(doc)


def get_nc_reference(doc):
    """Factura de compra referenciada por una NC (asignada por el usuario).

    Reemplaza la antigua busqueda de la referencia en el XML
    (cac:InvoiceDocumentReference): el proveedor no incluye la referencia
    cuando la factura referenciada ya fue aceptada, por lo que la NC se asigna
    manualmente en la vista (campo qp_ref_invoice = nvfac_nume de la PI).
    """
    return (doc or {}).get("qp_ref_invoice") or ""


def get_nc_reference_ctx(doc):
    """Contexto de la referencia de una NC tipo 5: (reference, pi_row).

    Retorna (reference, pi) o (None, None) si no se pudo resolver.
    """
    reference = get_nc_reference(doc)
    if not reference:
        return None, None
    pi = get_referenced_pi(reference)
    if not pi:
        return None, None
    return reference, pi


def get_devolution_bank(reference, pi):
    """Banco de lineas de la referencia: recepciones (tipo 1) u OC (tipo 2).

    Retorna (bank_lines, consumed_rows): bank_lines con qty original y
    consumed_rows lo ya devuelto para descontar. bank_lines es la lista de
    {item_code, qty, receiving_no, order_no} por linea de la referencia.
    """
    from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
        build_po_bank,
        build_receipt_bank,
    )

    gp_tipo = int((pi or {}).get("gp_tipo_factura_doc") or 0)
    purchase_order = (pi or {}).get("purchase_order_id") or ""

    if gp_tipo == GP_TIPO_ENVIO:
        receipts = frappe.get_all(
            "Purchase Receipt",
            filters={"qp_invoice": reference},
            fields=["name", "qp_supplier_oc"],
        )
        if not receipts:
            return [], get_consumed_devolutions(reference, pi)
        oc_by_receipt = {
            row.get("name"): row.get("qp_supplier_oc") or ""
            for row in receipts
        }
        items = frappe.get_all(
            "Purchase Receipt Item",
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
        items = frappe.get_all(
            "Purchase Order Item",
            filters={"parent": purchase_order,
                     "parenttype": "Purchase Order"},
            fields=["item_code", "qty", "idx", "uom"],
            order_by="idx",
        )
        bank = build_po_bank(items, order_no=purchase_order)

    consumed = get_consumed_devolutions(reference, pi)
    return bank, consumed


def get_consumed_devolutions(reference, pi):
    """Filas qp_SP_Devolution de la referencia (nombre de la PI)."""
    if not pi:
        return []
    return frappe.get_all(
        "qp_SP_Devolution",
        filters={"reference_invoice": pi.get("name")},
        fields=["item_code", "qty", "receiving_no", "order_no"],
    )


def persist_devolution_consumed(doc, reference, pi, assigned):
    """Registra el consumo del banco por linea (qp_SP_Devolution).

    Un fallo al registrar (p.ej. doctype sin migrar) NO debe tumbar la
    aprobacion de la factura: la creacion en GP/BC ya se persistio. Se
    loguea el error y se continua.
    """
    pi_name = (pi or {}).get("name") if isinstance(pi, dict) else pi
    if not pi_name or not assigned:
        return
    for line in (assigned or []):
        try:
            devolution = frappe.get_doc({
                "doctype": "qp_SP_Devolution",
                "reference_invoice": pi_name,
                "document_detail": doc.get("name"),
                "item_code": line.get("item_code"),
                "qty": line.get("qty") or 0,
                "receiving_no": line.get("receiving_no") or "",
                "order_no": line.get("order_no") or "",
            })
            devolution.insert(ignore_permissions=True)
        except Exception as error:
            frappe.log_error(
                message="{}: {}".format(
                    frappe.get_traceback(), str(error)
                ),
                title="Registrar devolucion qp_SP_Devolution",
            )


def get_reference_confirmation_id(pi):
    """confirmation_id de la qp_SP_PurchaseInvoiceBC de la referencia.

    En el flujo GP al crear la factura de referencia se inserta una
    qp_SP_PurchaseInvoiceBC con purchase_invoice = name de la PI. El proceso
    externo carga su confirmation_id (codigo que se usa como numero de
    recepcion para la NC tipo 5 con referencia tipo 2).
    """
    if not pi:
        return ""
    name = (pi or {}).get("name") if isinstance(pi, dict) else pi
    if not name:
        return ""
    return frappe.db.get_value(
        "qp_SP_PurchaseInvoiceBC",
        {"purchase_invoice": name},
        "confirmation_id",
    ) or ""


def get_nc_devolution_lines(doc, force=False):
    """Lineas del payload GP de una NC tipo 5 con el banco de la referencia.

    - Lineas de la NC: detail_lines homologadas (productos devueltos).
    - Banco: lineas de recepcion (tipo 1) u OC (tipo 2) de la factura de
      compra referenciada, menos lo ya devuelto (qp_SP_Devolution).
    - Asigna cada linea de la NC a una linea del banco y propaga su
      receiving_no/order_no. Si la devolucion excede el banco, la factura
      queda en error (no se envia) salvo force=True (aprobacion manual).
    - Referencia tipo 2: requiere que la factura de compra referenciada este
      confirmada (confirmation_id de su qp_SP_PurchaseInvoiceBC); si no lo
      esta, la NC no se envia (bloquea incluso con force) y muestra la alerta.
    - Anota en doc["_gp_nc_devolution"] = (reference, pi, assigned) para que
      la persistencia registre el consumo.
    """
    from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
        allocate_devolution,
        apply_consumed,
        excess_message,
    )

    reference, pi = get_nc_reference_ctx(doc)
    if not reference or not pi:
        return [], (
            "No se pudo obtener la factura de compra referenciada por la "
            "nota credito"
        )

    ref_is_tipo1 = (
        int((pi or {}).get("gp_tipo_factura_doc") or 0) == GP_TIPO_ENVIO
    )
    ref_confirmation = "" if ref_is_tipo1 else get_reference_confirmation_id(pi)
    if not ref_is_tipo1 and not ref_confirmation:
        return [], (
            "La factura de compra referenciada por la nota credito no ha sido "
            "confirmada"
        )

    product_lines, line_error = _get_lines_gp_from_invoice(doc)
    if line_error:
        return [], line_error

    bank, consumed = get_devolution_bank(reference, pi)
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
            # referencia asignada (noLineaRecepcion del banco).
            "idx": line.get("idx") or source.get("idx") or 0,
            "uom": source.get("uom") or "UN",
            "receiving_no": receiving_no,
            "order_no": line.get("order_no") or "",
        })

    doc["_gp_nc_devolution"] = (reference, pi, assigned)
    return payload_lines, ""


def get_referenced_pi(reference):
    """qp_SP_PurchaseInvoice referenciada por una NC.

    La referencia asignada por el usuario es el numero de factura del
    proveedor (nvfac_nume), no el name de la PI (que es "nit:nvfac_nume"). Se
    busca por nvfac_nume, detail (donde el flujo documenteme persiste
    nvfac_nume) o name. Retorna el dict {name, purchase_order_id,
    gp_tipo_factura_doc} o None.
    """
    if not reference:
        return None
    for filters in (
        {"name": reference},
        {"nvfac_nume": reference},
        {"detail": reference},
    ):
        row = frappe.db.get_value(
            "qp_SP_PurchaseInvoice",
            filters,
            ["name", "purchase_order_id", "gp_tipo_factura_doc"],
            as_dict=True,
        )
        if row:
            return row
    return None


def get_referenced_pi_gp_tipo(reference):
    """gp_tipo_factura_doc de la qp_SP_PurchaseInvoice referenciada.

    La referencia del XML es el numero de factura del proveedor (nvfac_nume),
    no el name de la PI (que es "nit:nvfac_nume"). Se busca por nvfac_nume,
    detail (donde el flujo documenteme persiste nvfac_nume) o name.
    """
    row = get_referenced_pi(reference)
    return row.get("gp_tipo_factura_doc") if row else None


def resolve_nc_gp_tipo_doc(doc):
    """Resuelve el tipoFacturaDoc (4 o 5) de una NC contra la DB real.

    Retorna (tipo, error). Con el tipo resuelto se decide si la NC se envia
    con tipofacturadoc = 4 (referencia a una CxP tipo 3) o tipofacturadoc = 5
    (referencia a una factura tipo 1/2).

    - Proveedor de servicio: siempre tipo 4, sin necesidad de referencia.
    - NC tipo 5: la referencia es la asignada por el usuario (qp_ref_invoice);
      si no tiene referencia asignada devuelve error (estado SR, no aprobable).
    """
    if is_service_supplier_doc(doc):
        return GP_TIPO_NC, ""
    reference = get_nc_reference(doc)
    if not reference:
        return None, (
            "La nota de credito no tiene una factura de compra de "
            "referencia asignada"
        )
    return resolve_nc_tipo_for_doc(
        doc,
        get_reference_fn=lambda d: get_nc_reference(d),
        get_referenced_tipo_fn=get_referenced_pi_gp_tipo,
    )


def parse_doc_numbers(response):
    """Resultados por factura: lista de {doc_number, error} en el mismo
    orden del payload enviado a BC."""
    if not isinstance(response, dict):
        return []
    return response.get("invoices") or []


def resolve_doc_number_via_odata(doc):
    from qp_supplier_front.infrastructure.adapters.fetch_oauth_adapter import (
        fetch_invoices,
    )

    vendor = doc.get("nvpro_ndoc")
    if not vendor:
        return None
    invoice_date = str(doc.get("nvfac_fech") or "")[:10]
    param = "$filter=Vendor_No eq '{}' and Document_Type eq 'Invoice'".format(vendor)
    if invoice_date:
        param += " and Posting_Date eq {}".format(invoice_date)
    try:
        result = fetch_invoices("list_purchase_invoice", param=param)
    except Exception:
        return None
    values = result.get("value") or []
    if not values:
        return None
    return values[0].get("Document_No")


def _capture_gp_tipo(build_invoice_fn):
    """Envuelve el builder GP para anotar en el doc el tipoFacturaDoc enviado.

    El core de aprobacion pasa el mismo dict `doc` de construccion a
    persistencia: la clave transitoria "_gp_tipo_factura_doc" queda disponible
    para que persist_invoice lo guarde en la factura creada.
    Retorna la funcion build original si no puede anotar el tipo.
    """
    def build(doc, lines, headquarter):
        invoice = build_invoice_fn(doc, lines, headquarter)
        tipo = None
        if isinstance(invoice, dict):
            tipo = invoice.get("tipoFacturaDoc")
        doc["_gp_tipo_factura_doc"] = tipo
        return invoice
    return build


def _persist_gp_tipo(doc):
    """Guarda el tipoFacturaDoc anotado en el doc sobre la factura creada.

    No hace nada si el builder no anoto tipo (flujo BC o tipo no resuelto).
    """
    tipo = (doc or {}).get("_gp_tipo_factura_doc")
    name = (doc or {}).get("name")
    if tipo is None or not name:
        return
    frappe.db.set_value(
        "qp_SP_PurchaseInvoice", name, "gp_tipo_factura_doc", tipo
    )


def _persist_nc_devolution(doc):
    """Registra el consumo del banco de la NC tipo 5 (si fue asignado).

    Lee del doc la clave transitoria "_gp_nc_devolution" = (reference, pi,
    assigned) seteada por get_nc_devolution_lines durante el armado del
    payload y persiste cada linea en qp_SP_Devolution.
    """
    devolution = (doc or {}).get("_gp_nc_devolution")
    if not devolution or not isinstance(devolution, tuple) or len(devolution) != 3:
        return
    reference, pi, assigned = devolution
    persist_devolution_consumed(doc, reference, pi, assigned)


def persist_invoice(doc, doc_number, now, sync_flow="BC"):
    from qp_supplier_front.infrastructure.adapters.filter_adapter import (
        get_existing_ids,
    )
    from qp_supplier_front.infrastructure.strategies.gp.persist_adapter import (
        insert_invoices,
    )

    if not doc_number:
        doc_number = resolve_doc_number_via_odata(doc)
    if not doc_number:
        doc_number = doc.get("nvfac_nume") or doc.get("name")

    existing = get_existing_ids("qp_SP_PurchaseInvoice", "invoice_id", {doc_number})
    if doc_number in existing:
        return doc_number

    # Idempotencia por name: un reintento puede re-aprobar la misma factura
    # (o un intento previo pudo quedar a medias) con un doc_number distinto.
    # El name de la PI es fijo (name del documento); si ya existe, no insertar.
    existing_names = get_existing_ids(
        "qp_SP_PurchaseInvoice", "name", {doc.get("name")}
    )
    if doc.get("name") in existing_names:
        return doc_number

    supplier = get_supplier_by_tax_id(doc.get("nvpro_ndoc"))
    invoice_date = str(doc.get("nvfac_fech") or "")[:10]

    invoice_tuple = (
        doc.get("name"),
        doc_number,
        "Abierto",
        invoice_date or None,
        now[:10],
        doc.get("nvmon_codi") or "COP",
        doc.get("nvfac_stot") or 0,
        doc.get("nvfac_viva") or 0,
        doc.get("nvfac_totp") or 0,
        supplier,
        doc.get("nvfac_nume") or "",
        doc.get("nvfac_orde") or "",
        sync_flow,
        now,
        now,
        "Administrator",
        "Administrator",
    )
    insert_invoices({doc.get("name"): invoice_tuple}, now)

    _persist_gp_tipo(doc)
    _persist_nc_devolution(doc)
    _create_purchase_invoice_bc(doc_number, doc.get("name"))
    return doc_number


def _persist_for_backend(sync_flow):
    """Envoltorio de persist_invoice con el flujo de sincronizacion fijado
    (BC o GP). Mantiene la firma (doc, doc_number, now) del core."""
    def persist(doc, doc_number, now):
        return persist_invoice(doc, doc_number, now, sync_flow=sync_flow)

    return persist


def _create_purchase_invoice_bc(doc_number, document_detail_name):
    """Inserta la referencia BC -> PurchaseInvoice para el flujo de confirmacion.

    El nuevo doctype qp_SP_PurchaseInvoiceBC usa como name el codigo que BC
    devuelve (invoice_id) y referencia al qp_SP_PurchaseInvoice. El proceso
    externo completara el confirmation_id mediante el PUT estandar de Frappe.
    """
    if not doc_number or not document_detail_name:
        return
    if frappe.db.exists("qp_SP_PurchaseInvoiceBC", doc_number):
        return
    bc_doc = frappe.get_doc({
        "doctype": "qp_SP_PurchaseInvoiceBC",
        "invoice_id": doc_number,
        "purchase_invoice": document_detail_name,
    })
    bc_doc.insert(ignore_permissions=True)


def mark_registered(doc, doc_number):
    from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
        RealTimelineAdapter,
    )
    RealTimelineAdapter(frappe_module=frappe).set_state(doc.get("name"), "BCC")
    doc["nvfac_esta"] = "BCC"
    resolve_open_alerts(doc.get("name"))


def mark_error(doc, error):
    insert_alert(doc.get("name"), error, _make_now(), alert_type="ErrorUrgente")


def mark_duplicate_registered(doc, error, now):
    """Marca una factura duplicada como creada en BC y detiene el reintento.

    Al recibir "Ya existe la factura de compra..." de BC, el codigo BC no es
    recuperable: se detiene el reintento de creacion, se fija la factura en
    "BCC" (Creada en BC) y se inserta una alerta indicando que falta el codigo
    BC, para gestion manual. No se crea la referencia (qp_SP_PurchaseInvoice /
    qp_SP_PurchaseInvoiceBC) porque un invoice_id falso romperia el enlace de
    la confirmacion externa.
    """
    from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
        RealTimelineAdapter,
    )
    RealTimelineAdapter(frappe_module=frappe).set_state(doc.get("name"), "BCC")
    doc["nvfac_esta"] = "BCC"
    resolve_open_alerts(doc.get("name"))
    insert_alert(
        doc.get("name"),
        (
            "La factura ya existe en BC; se detuvo el reintento. "
            "No se pudo obtener el codigo BC para enlazar su confirmacion. "
            "Error: {}".format(error)
        ),
        now,
        alert_type="ErrorUrgente",
    )


def send_purchase_invoice_request(endpoint_code, payload):
    response = frappe.call(
        "qp_middleware.qp_middleware.service.purchase_invoice.sync.create_purchase_invoices",
        payload=payload,
        endpoint_code=endpoint_code,
    )
    try:
        import html

        from qp_supplier_front.services.utils import add_log

        raw_response = None
        log_response = response
        if isinstance(response, dict) and response.get("raw_response") is not None:
            raw_response = html.unescape(response.get("raw_response") or "")
            log_response = dict(response)
            log_response.pop("raw_response", None)

        add_log(
            title="Aprobacion documenteme -> BC ({})".format(endpoint_code),
            payload=payload,
            response=log_response,
            raw_response=raw_response,
        )
    except Exception:
        pass
    return response, 200


# Llaves donde GP puede devolver el numero de comprobante (se busca en orden).
# voucherNumber es la respuesta estandar del endpoint alpla.
_GP_DOC_NUMBER_KEYS = (
    "voucherNumber",
    "invoiceId",
    "invoiceNumber",
    "Document_No",
    "documentNumber",
    "docNumber",
    "noFacturaProveedor",
    "return_value",
)

# statusCode que GP/alpla devuelve cuando la creacion fue exitosa.
_GP_SUCCESS_STATUS_CODES = ("1",)

# statusCode que GP devuelve cuando el documento de la factura ya existe
# (VNDDOCNM duplicado). Se contiene como "ya registrado" igual que BC con
# "ya existe la factura de compra".
_GP_DUPLICATE_STATUS_CODES = ("996",)

_GP_NO_DOC_NUMBER_MSG = "GP no devolvio documento de la factura"
_GP_INVOICE_REJECTED_MSG = "GP rechazo la creacion de la factura (statusCode {})"


def _extract_gp_doc_number(node):
    """Numero de factura GP desde un nodo (dict o lista) o vacio si no existe."""
    if isinstance(node, dict):
        for key in _GP_DOC_NUMBER_KEYS:
            value = node.get(key)
            if value:
                return str(value).strip()
        for value in node.values():
            found = _extract_gp_doc_number(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and not item.get("error"):
                found = _extract_gp_doc_number(item)
                if found:
                    return found
            elif isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def _extract_gp_error(node):
    """Mensaje de error legible desde la respuesta GP (o vacio si no hay).

    GP/alpla describe los errores en "description" (lowerCamelCase) ademas de
    las variantes ya soportadas (Description/Message/error...).
    """
    if isinstance(node, dict):
        if node.get("error"):
            return str(node.get("error"))
        for key in ("Description", "Message", "message", "description",
                    "errorInterno", "errorMessage", "error_message"):
            if node.get(key):
                return str(node.get(key))
        for value in node.values():
            found = _extract_gp_error(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _extract_gp_error(item)
            if found:
                return found
    return ""


def _extract_gp_status_code(node):
    """statusCode de la respuesta GP (string) o None si no es informativo.

    GP/alpla devuelve "1" en exito y codigos de error (996, 2005, 2061...)
    cuando la peticion falla, con HTTP 200 o 400 segun el caso. Los valores
    vacios o "0" se ignoran (no aportan clasificacion).
    """
    if not isinstance(node, dict):
        return None
    for key in ("statusCode", "StatusCode"):
        code = node.get(key)
        if code in (None, "", 0, "0"):
            continue
        return str(code)
    return None


def _gp_duplicate_message(node):
    """Mensaje de contencion cuando el documento ya existe en GP (VNDDOCNM).

    Contiene el marcador que el core reconoce como "ya registrado"
    (is_invoice_already_registered) para detener los reintentos y marcar la
    factura BCC sin numero de comprobante recuperable.
    """
    message = (
        "Ya existe la factura de compra en GP; el numero de documento del "
        "proveedor (VNDDOCNM) debe ser unico y ya fue usado. GP no devolvio "
        "el numero de comprobante."
    )
    detail = _extract_gp_error(node)
    if detail:
        message += " Error: {}".format(detail)
    return message


def _gp_invoices(doc_number, num_invoices, error=""):
    """Contrato BC con un resultado replicado a num_invoices (orden del payload)."""
    return {
        "Result": 0,
        "invoices": [
            {"doc_number": doc_number, "error": error}
            for _ in range(max(num_invoices, 1))
        ],
    }


def _gp_global_error(response, fallback):
    """Error global GP con mensaje legible (description si existe)."""
    message = _extract_gp_error(response)
    return {
        "Result": 1,
        "Description": message or fallback,
        "invoices": [],
    }


def _normalize_gp_node(node):
    """Un resultado GP individual -> {"doc_number", "error"} del contrato BC.

    - statusCode "1" (exito) con voucherNumber: doc_number con error vacio.
    - statusCode 996 (duplicado): doc_number vacio con error contencion.
    - cualquier otro statusCode: error global con la descripcion legible.
    - sin statusCode (shape legacy): se intenta extraer el numero de documento.
    """
    if not isinstance(node, dict):
        return {"doc_number": "", "error": "Resultado GP invalido"}
    status_code = _extract_gp_status_code(node)
    if status_code in _GP_DUPLICATE_STATUS_CODES:
        return {"doc_number": "", "error": _gp_duplicate_message(node)}
    if status_code in _GP_SUCCESS_STATUS_CODES:
        doc_number = _extract_gp_doc_number(node)
        if not doc_number:
            return {"doc_number": "", "error": _GP_NO_DOC_NUMBER_MSG}
        return {"doc_number": doc_number, "error": ""}
    if status_code is not None:
        return {
            "doc_number": "",
            "error": _extract_gp_error(node)
            or _GP_INVOICE_REJECTED_MSG.format(status_code),
        }
    doc_number = _extract_gp_doc_number(node)
    if not doc_number:
        return {
            "doc_number": "",
            "error": _extract_gp_error(node) or _GP_NO_DOC_NUMBER_MSG,
        }
    return {"doc_number": doc_number, "error": _extract_gp_error(node)}


def normalize_gp_response(response, status, num_invoices=1):
    """Convierte la respuesta GP al contrato BC para no tocar el core.

    Retorna {"Result": 0, "invoices": [{doc_number, error}, ...]} con un
    resultado por factura (en el mismo orden del payload) o
    {"Result": 1, "Description": ..., "invoices": []} para errores globales.

    La respuesta alpla puede tener varias formas:
    - Contrato BC (Result/invoices): se reutiliza tal cual.
    - Resultado individual (statusCode/description/voucherNumber): statusCode
      "1" con voucherNumber es exito; "996" es un documento ya existente (se
      contiene como duplicado igual que BC); cualquier otro statusCode es
      error con la descripcion legible.
    - Lista de resultados individuales (uno por factura del payload): cada
      elemento se mapea a su factura.
    [A DEFINIR] Ajustar en cuanto se tenga la spec exacta del endpoint.
    """
    if isinstance(response, dict) and response.get("Result") is not None \
            and "invoices" in response:
        return response
    if isinstance(response, dict) and response.get("Result") == 1:
        return response

    if isinstance(response, list):
        return _normalize_gp_results(response, num_invoices)

    status_code = _extract_gp_status_code(response)
    if status_code is not None:
        if status_code in _GP_SUCCESS_STATUS_CODES:
            doc_number = _extract_gp_doc_number(response)
            if not doc_number:
                return {
                    "Result": 1,
                    "Description": _GP_NO_DOC_NUMBER_MSG,
                    "invoices": [],
                }
            return _gp_invoices(doc_number, num_invoices)
        if status_code in _GP_DUPLICATE_STATUS_CODES:
            return _gp_invoices(
                "", num_invoices, error=_gp_duplicate_message(response)
            )
        return _gp_global_error(
            response, _GP_INVOICE_REJECTED_MSG.format(status_code)
        )

    if status not in (200, 201):
        return _gp_global_error(response, response or "Error en la peticion a GP")
    if not isinstance(response, dict):
        return _gp_global_error(response, response or "Respuesta invalida de GP")

    doc_number = _extract_gp_doc_number(response)
    if not doc_number:
        return _gp_global_error(response, _GP_NO_DOC_NUMBER_MSG)
    return _gp_invoices(doc_number, num_invoices, error=_extract_gp_error(response))


def _normalize_gp_results(results, num_invoices):
    """Mapea una lista de resultados GP a las facturas del payload (por indice).

    Tolerancia de longitud: si GP devuelve mas elementos que facturas se
    ignoran los sobrantes; si devuelve menos, las facturas sin resultado
    quedan con error.
    """
    results = list(results or [])
    if not results:
        return _gp_global_error(
            results, "GP devolvio una lista vacia de resultados"
        )
    invoices = []
    for idx in range(max(num_invoices, 1)):
        node = results[idx] if idx < len(results) else None
        if node is None:
            invoices.append({
                "doc_number": "",
                "error": "GP no devolvio resultado para la factura",
            })
            continue
        invoices.append(_normalize_gp_node(node))
    return {"Result": 0, "invoices": invoices}


def send_purchase_invoice_request_gp(endpoint_code, payload):
    """Envio de creacion de facturas a GP (bearer alpla).

    A diferencia de BC (que recibe el arreglo completo en el middleware), el
    endpoint GP espera UN objeto por peticion (DtoPurchasePOPM). Por eso el
    payload (lista de facturas) se envia factura a factura y cada respuesta
    se normaliza al contrato BC. El retorno combina los resultados en
    {"Result": 0, "invoices": [un resultado por factura, mismo orden]}.

    El HTTP status del retorno es 200 porque el core procesa cada resultado
    individual (aprobacion, duplicado o error) sin abortar el lote por el
    status de una peticion puntual.
    """
    from qp_authorization.use_case.bearer.authorize import send_request_status

    invoices = payload if isinstance(payload, list) else [payload or {}]
    combined = []
    for invoice in invoices:
        response, status = send_request_status(
            endpoint_code, payload=invoice
        )
        try:
            from qp_supplier_front.services.utils import add_log

            add_log(
                title="Aprobacion documenteme -> GP ({})".format(endpoint_code),
                payload=invoice,
                response=response,
            )
        except Exception:
            pass
        normalized = normalize_gp_response(
            response, status, num_invoices=1
        )
        slot = (normalized.get("invoices") or [{}])[0]
        if not slot:
            slot = {
                "doc_number": "",
                "error": normalized.get("Description")
                or "GP rechazo la factura",
            }
        combined.append(slot)
    return {"Result": 0, "invoices": combined}, 200


# =========================================================================
# Orquestacion compartida
# =========================================================================
def _get_lines_for_selected(base_get_lines, selected_receipts, data):
    """get_lines restringido a los recibos de la seleccion manual.

    En modo real lee los items de SOLO los recibos vinculados al doc
    (get_lines_from_receipts con receipt_names); en simulador delega en el
    get_lines del bundle (lineas de la factura del proveedor en memoria).
    """

    def get_selected_lines(doc):
        receipt_names = ((selected_receipts or {}).get(doc.get("name")) or [])
        if not receipt_names:
            return [], "La factura no tiene recepciones seleccionadas"
        if data is not None:
            return base_get_lines(doc)
        return get_lines_from_receipts(
            doc.get("nvfac_orde"), receipt_names=receipt_names
        ), ""

    return get_selected_lines


def approve_documents_core(doc_names, send_request_fn=None, force=False,
                           selected_receipts=None, backend="BC"):
    components = runtime.resolve()
    if send_request_fn is None:
        if backend == "GP":
            send_request_fn = components.get("approve_send_gp_fn") \
                or send_purchase_invoice_request_gp
        else:
            send_request_fn = components.get("approve_send_fn") \
                or send_purchase_invoice_request
    cb = components.get("approve_callbacks") or {}
    is_service_supplier_fn = None
    resolve_supplier_rule_fn = None
    if backend == "GP":
        get_lines_fn = cb.get("get_lines_gp_fn")
        if get_lines_fn is None:
            resolve_nc_tipo_fn = cb.get(
                "resolve_nc_tipo_fn", resolve_nc_gp_tipo_doc)
            get_lines_fn = lambda doc: get_lines_gp(
                doc, resolve_nc_tipo_fn=resolve_nc_tipo_fn, force=force)
        elif force:
            base_get_lines_fn = get_lines_fn
            get_lines_fn = lambda doc: base_get_lines_fn(doc, force=force)
        if selected_receipts is not None:
            get_lines_fn = _get_lines_for_selected(
                get_lines_fn, selected_receipts, components.get("data")
            )
        build_invoice_fn = cb.get("build_invoice_fn")
        if build_invoice_fn is None:
            build_invoice_fn = make_invoice_builder(
                "documenteme",
                backend="GP",
                resolve_tipo_fn=cb.get(
                    "resolve_gp_tipo_fn", resolve_gp_tipo_for_doc
                ),
                get_oc_dates_fn=cb.get("get_po_dates_fn", get_po_dates),
                resolve_nc_tipo_fn=cb.get(
                    "resolve_nc_tipo_fn", resolve_nc_gp_tipo_doc
                ),
            )
        build_invoice_fn = _capture_gp_tipo(build_invoice_fn)
        is_service_supplier_fn = cb.get("is_service_supplier_fn", is_service_supplier_doc)
        resolve_supplier_rule_fn = cb.get(
            "resolve_supplier_rule_fn", resolve_supplier_rule)
    else:
        get_lines_fn = cb.get("get_lines_fn", get_lines)
        if selected_receipts is not None:
            get_lines_fn = _get_lines_for_selected(
                get_lines_fn, selected_receipts, components.get("data")
            )
        build_invoice_fn = cb.get("build_invoice_fn")
    sync_flow = "GP" if backend == "GP" else "BC"
    persist_invoice_fn = cb.get("persist_invoice_fn")
    if persist_invoice_fn is None:
        persist_invoice_fn = _persist_for_backend(sync_flow)
    else:
        _base_persist = persist_invoice_fn

        def _persist_with_sync_flow(doc, doc_number, now):
            return _base_persist(doc, doc_number, now, sync_flow=sync_flow)

        persist_invoice_fn = _persist_with_sync_flow
    result = approve_documents(
        doc_names,
        get_docs_fn=cb.get("get_docs_fn", get_docs),
        get_lines_fn=get_lines_fn,
        get_headquarter_fn=cb.get("get_headquarter_fn", get_headquarter),
        po_exists_fn=cb.get("po_exists_fn", po_exists),
        receipts_total_fn=cb.get("receipts_total_fn", receipts_total),
        receipt_bank_fn=cb.get("receipt_bank_fn", receipt_bank),
        consume_receipts_fn=cb.get("consume_receipts_fn", consume_receipts),
        send_request_fn=send_request_fn or send_purchase_invoice_request,
        parse_doc_numbers_fn=parse_doc_numbers,
        persist_invoice_fn=persist_invoice_fn,
        mark_registered_fn=cb.get("mark_registered_fn", mark_registered),
        mark_error_fn=cb.get("mark_error_fn", mark_error),
        mark_duplicate_registered_fn=cb.get(
            "mark_duplicate_registered_fn", mark_duplicate_registered),
        commit_fn=frappe.db.commit,
        now=_make_now(),
        force=force,
        resolve_rule_fn=cb.get("resolve_rule_fn", _resolve_rule),
        selected_receipts=selected_receipts,
        build_invoice_fn=build_invoice_fn,
        is_service_supplier_fn=is_service_supplier_fn,
        resolve_supplier_rule_fn=resolve_supplier_rule_fn,
    )

    on_batch_approved = components["on_batch_approved_fn"]
    if on_batch_approved is not None:
        on_batch_approved(result)

    return result


def run_approve_with_receipts(doc_names, selected_receipts,
                              send_request_fn=None, backend="BC"):
    """Aprueba facturas cuya seleccion manual de recibos ya fue aplicada.

    Los recibos ya estan vinculados (qp_invoice = nvfac_nume); esta funcion
    reutiliza el pipeline de aprobacion (crear en BC -> BCC) pero con el set
    explicito del usuario, sin re-runnear pack_oc_group.
    """
    result = approve_documents_core(
        doc_names,
        send_request_fn=send_request_fn,
        force=False,
        selected_receipts=selected_receipts,
        backend=backend,
    )
    frappe.db.commit()
    return result


def get_nc_devolution_excess(doc, data=None):
    """Pre-validacion del banco de una NC tipo 5 (mensaje) sin efectos.

    Calcula si la devolucion excede el banco de la factura de referencia (sin
    persistir ni anotar el doc). Usado por la pre-validacion del front, que
    SÍ puede confirmarse manualmente (force=True): el exceso es una advertencia.

    La falta de confirmation_id en la referencia NO se reporta aqui: es un
    bloqueo duro (no forceable), solo se valida al aprobar en
    get_nc_devolution_lines y deja alerta en la factura.

    Con data (facade en simulacion) delega en el espejo de memoria.
    """
    if data is not None and hasattr(data, "devolution_excess"):
        return data.devolution_excess(doc)
    from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
        allocate_devolution,
        apply_consumed,
        excess_message,
    )

    reference, pi = get_nc_reference_ctx(doc)
    if not reference or not pi:
        return ""
    product_lines, line_error = _get_lines_gp_from_invoice(doc)
    if line_error:
        return ""
    bank, consumed = get_devolution_bank(reference, pi)
    available = apply_consumed(bank, consumed)
    _, excess = allocate_devolution(product_lines, available)
    return excess_message(excess)


def collect_document_violations(doc_names, backend="BC"):
    """Advertencias de aprobacion automatica por factura (pre-validacion).

    Sin efectos secundarios: solo lee los documentos y retorna
    [{"nvfac_nume", "violations": [...]}] para las facturas que no cumplen
    la regla OC - recepcion - montos pero aun pueden aprobarse de forma
    forzada por el usuario. Con backend GP los proveedores de servicio
    relajan OC/recepciones (solo su propia regla de rechazo aplica).

    Con backend GP ademas se reporta el exceso del banco de devoluciones de
    las NC tipo 5 (Nvtip_docu == "C" que referencia facturas tipo 1/2) para
    que el front muestre la confirmacion antes de aprobar manualmente.
    En simulacion usa el bundle de memoria (get_docs/exceso).
    """
    components = runtime.resolve()
    cb = components.get("approve_callbacks") or {}
    data = components.get("data")
    get_docs_fn = cb.get("get_docs_fn", get_docs)
    docs = get_docs_fn(doc_names)
    violations = collect_registrable_violations(
        docs,
        po_exists,
        receipt_bank,
        resolve_rule_fn=_resolve_rule,
        is_service_supplier_fn=(
            is_service_supplier_doc if backend == "GP" else None
        ),
        resolve_supplier_rule_fn=(
            resolve_supplier_rule if backend == "GP" else None
        ),
    )
    if backend != "GP":
        return violations

    by_nume = {v.get("nvfac_nume"): v for v in violations}
    for doc in (docs or []):
        if not is_credit_note(doc.get("nvtip_docu")):
            continue
        excess = get_nc_devolution_excess(doc, data=data)
        if not excess:
            continue
        entry = by_nume.setdefault(
            doc.get("nvfac_nume"),
            {"nvfac_nume": doc.get("nvfac_nume"), "violations": []},
        )
        if excess not in entry["violations"]:
            entry["violations"].append(excess)
    return list(by_nume.values())


def run_approve(doc_names_raw, send_request_fn=None, force=False, backend="BC"):
    """Flujo manual: valida permisos y aprueba el lote seleccionado.

    Con force=True (el usuario confirmo las violaciones en el front) se
    omiten las advertencias de OC - recepcion - montos; los estados
    definitivos/en proceso siguen bloqueando.

    backend ("BC" o "GP") selecciona el origen de la creacion de factura
    (builder, envio y persistencia).
    """
    doc_names = parse_json(doc_names_raw)

    if not _has_permission(frappe.get_roles()):
        response(403, "No tiene permisos para aprobar facturas")
        return

    result = approve_documents_core(
        doc_names, send_request_fn=send_request_fn, force=force, backend=backend
    )
    frappe.db.commit()

    errors = result.get("errors") or []

    for err in errors:
        frappe.log_error(
            message="Factura {}: {}".format(
                err.get("nvfac_nume"), err.get("error")
            ),
            title="Aprobar documenteme - error",
        )

    result["backend"] = backend

    if errors:
        detail = ", ".join(
            "{}: {}".format(err.get("nvfac_nume"), err.get("error"))
            for err in errors
        )
        response(500, "Error al aprobar: {}".format(detail), result)
        return

    response(200, "Factura(s) aprobada(s) correctamente", result)
