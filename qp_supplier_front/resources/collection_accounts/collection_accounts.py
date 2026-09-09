import frappe

from qp_supplier_front.resources.collection_accounts import runtime


def _get_current_available_amount(purchase_order_name):
    purchase_order = frappe.db.get_value(
        "Purchase Order",
        purchase_order_name,
        ["name", "supplier", "grand_total", "currency"],
        as_dict=True,
    )

    if not purchase_order:
        frappe.throw("La orden de compra no existe.")

    total_due = float(purchase_order.get("grand_total") or 0)
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
    """Crea la cuenta de cobro y dispara la creacion de la factura.

    En modo simulador (runtime) crea la cuenta y la factura en memoria sin
    tocar la base de datos. En modo real inserta la cuenta (el hook
    on_insert crea y evalua el qp_SP_PurchaseInvoice asociado).
    """
    if runtime.is_simulation_enabled():
        components = runtime.resolve()
        create_fn = components.get("create_account_fn")
        if create_fn is not None:
            result = create_fn(
                purchase_order,
                amount_to_invoice,
                observations=observations,
                docs=docs,
            )
            if isinstance(result, dict) and result.get("error"):
                frappe.throw(result["error"])
            return result

    purchase_order_doc, total_due, available_amount = _get_current_available_amount(purchase_order)

    amount_to_invoice = float(amount_to_invoice or 0)

    if amount_to_invoice <= 0:
        frappe.throw("El monto a facturar debe ser mayor a cero.")

    if amount_to_invoice > available_amount:
        frappe.throw(
            f"El monto a facturar no puede ser mayor al valor disponible ({frappe.format_value(available_amount, 'Currency', currency=purchase_order_doc.get('currency') or 'COP')})."
        )

    collection_account = frappe.new_doc("qp_SP_CollectionAccounts")
    collection_account.supplier_id = purchase_order_doc.get("supplier")
    collection_account.purchase_order = purchase_order_doc.get("name")
    collection_account.total_due = total_due
    collection_account.available_amount = available_amount
    collection_account.amount_payable = amount_to_invoice
    collection_account.observations = observations
    collection_account.creation_date = frappe.utils.nowdate()

    if docs:
        collection_account.docs = docs

    collection_account.insert(ignore_permissions=True)

    # Camino redundante: crea y evalua el PI inmediatamente en el mismo
    # request (no depende de que el doc_events esté registrado/cargado).
    if runtime.resolve().get("data") is None:
        pi_name = create_purchase_invoice_for_collection_account(collection_account)
        if pi_name:
            evaluate_purchase_invoice(pi_name)

    return {
        "name": collection_account.name,
        "available_amount": available_amount,
        "amount_payable": amount_to_invoice,
        "purchase_invoice": collection_account.get("purchase_invoice") or pi_name,
    }


def on_collection_account_insert(doc, method):
    """Hook on_insert de qp_SP_CollectionAccounts: crea y evalua la factura.

    En modo simulador el flujo no inserta en la base de datos real (la cuenta
    vive en memoria), por lo que este hook no aplica.
    """
    try:
        if runtime.resolve().get("data") is not None:
            return

        purchase_invoice_name = create_purchase_invoice_for_collection_account(doc)
        if purchase_invoice_name:
            evaluate_purchase_invoice(purchase_invoice_name)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="on_collection_account_insert",
        )
        raise


def _guess_file_type(file_name):
    """Tipo de archivo derivado de la extension (p. ej. 'png', 'PDF')."""
    parts = (file_name or "").rsplit(".", 1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip().upper()
    return ""


def _attach_docs(purchase_invoice, docs):
    """Registra el archivo adjunto de la cuenta de cobro (docs) en el child
    docs_attach de la factura, igual que documenteme con su tabla de adjuntos.

    Se invoca ANTES del insert (el child se persiste con la factura): evita el
    segundo save que generaria un mismatch de timestamp. El archivo fue subido
    por el front (upload_file) y existe como File de Frappe; se resuelve para
    completar file_name/file_id. El tipo se deriva de la extension (el doctype
    File de Frappe no expone content_type en esta version).
    """
    docs = (docs or "").strip()
    if not docs:
        return

    from posixpath import basename

    file_name = basename(docs.split("?", 1)[0]) or "documento"
    file_id = frappe.db.get_value("File", {"file_url": docs}, "name") or ""

    if file_id:
        try:
            file_doc = frappe.get_doc("File", file_id)
            if (file_doc.file_name or "").strip():
                file_name = file_doc.file_name.strip()
        except Exception:
            pass

    purchase_invoice.append("docs_attach", {
        "file_name": file_name,
        "file_type": _guess_file_type(file_name),
        "file_url": docs,
        "file_id": file_id,
    })


def create_purchase_invoice_for_collection_account(collection_account_doc):
    """Crea el qp_SP_PurchaseInvoice a partir de la cuenta de cobro (real)."""
    existing = frappe.db.get_value(
        "qp_SP_PurchaseInvoice",
        {"collection_account": collection_account_doc.name},
        "name",
    )
    if existing:
        return existing

    supplier = collection_account_doc.get("supplier_id")
    tax_id = frappe.db.get_value("Supplier", supplier, "tax_id")
    po_name = collection_account_doc.get("purchase_order")
    po = frappe.db.get_value(
        "Purchase Order", po_name, ["grand_total", "currency"], as_dict=True
    ) or {}
    amount = float(collection_account_doc.get("amount_payable") or 0)
    now = frappe.utils.nowdate()

    purchase_invoice = frappe.new_doc("qp_SP_PurchaseInvoice")
    purchase_invoice.qp_status = "E"
    purchase_invoice.status = "Abierto"
    purchase_invoice.qp_sync_flow = "COLLECTION"
    purchase_invoice.supplier = supplier
    purchase_invoice.purchase_order_id = po_name
    purchase_invoice.nvpro_ndoc = tax_id or supplier
    purchase_invoice.nvfac_fech = collection_account_doc.get("creation_date") or now
    purchase_invoice.nvfac_conv = "2"
    purchase_invoice.currency = po.get("currency") or "COP"
    purchase_invoice.subtotal = amount
    purchase_invoice.tax = 0
    purchase_invoice.total = amount
    purchase_invoice.collection_account = collection_account_doc.name
    purchase_invoice.registration_date = now
    _attach_docs(purchase_invoice, collection_account_doc.get("docs"))
    purchase_invoice.insert(ignore_permissions=True)

    frappe.db.set_value(
        "qp_SP_PurchaseInvoice", purchase_invoice.name, "nvfac_nume", purchase_invoice.name
    )
    frappe.db.set_value(
        "qp_SP_CollectionAccounts",
        collection_account_doc.name,
        "purchase_invoice",
        purchase_invoice.name,
    )
    return purchase_invoice.name


def evaluate_purchase_invoice(purchase_invoice_name):
    """Valida la factura creada (regla de credito: banco de recepciones) y
    fija V, o la deja en E y la asigna automaticamente.

    Las facturas de cuentas de cobro son de CREDITO (nvfac_conv="2"): exigen
    una combinacion exacta de recepciones no consumidas que cubra el monto.
    Si la cubren -> V. Si no la cubren -> E (sin notificacion ErrorUrgente, no
    es un error) y se dispara la asignacion automatica a los usuarios
    configurados.
    """
    from qp_supplier_front.uses_cases.collection_invoices import mapping

    components = runtime.resolve()
    callbacks = components.get("evaluate_callbacks") or {}
    po_exists_fn = callbacks.get("po_exists_fn")
    receipt_bank_fn = callbacks.get("receipt_bank_fn")
    if po_exists_fn is None or receipt_bank_fn is None:
        return None

    purchase_invoice = frappe.get_doc("qp_SP_PurchaseInvoice", purchase_invoice_name)
    doc = mapping.build_document_dict(purchase_invoice.as_dict())

    resolve_rule_fn = callbacks.get("resolve_rule_fn")

    warnings = mapping.collect_validation_violations(
        [doc], po_exists_fn, receipt_bank_fn,
        resolve_rule_fn=resolve_rule_fn,
    )

    if warnings:
        first = (warnings[0].get("violations") or [""])[0]
        frappe.db.set_value(
            "qp_SP_PurchaseInvoice",
            purchase_invoice_name,
            {"qp_status": "E", "qp_error_message": first},
        )

        # No cubre el banco de recepciones: asignacion automatica.
        from qp_supplier_front.resources.collection_accounts import auto_assign
        auto_assign.run_collection_auto_assign([purchase_invoice_name])
        return False

    frappe.db.set_value(
        "qp_SP_PurchaseInvoice",
        purchase_invoice_name,
        {"qp_status": "V", "qp_error_message": ""},
    )
    from qp_supplier_front.resources.collection_accounts._notifications import (
        resolve_open_notifications,
    )
    resolve_open_notifications(purchase_invoice_name)
    return True