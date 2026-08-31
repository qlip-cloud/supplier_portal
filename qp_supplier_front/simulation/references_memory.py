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