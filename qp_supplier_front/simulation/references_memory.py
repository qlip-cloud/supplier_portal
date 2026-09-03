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


def memory_resolve_rule(store, doc):
    """Regla activa (proveedor con fallback al default del MasterSetup).

    Espejo de resources/documenteme/auto_reject.resolve_rule sobre el store.
    Devuelve None si no hay regla activa (equivale a "no action").
    """
    from qp_supplier_front.simulation.master_setup_source import (
        MemoryMasterSetupSource,
    )
    from qp_supplier_front.uses_cases.documenteme.auto_reject import (
        resolve_auto_reject_config,
    )

    supplier = memory_get_supplier_by_tax_id(store, doc.get("nvpro_ndoc"))
    supplier_rule = None
    if supplier:
        supplier_rule = memory_get_rule(
            store, memory_get_supplier_auto_reject_rule(store, supplier))

    setup_rule = memory_get_rule(
        store, MemoryMasterSetupSource(store).auto_reject_rule())

    return resolve_auto_reject_config(supplier_rule, setup_rule)