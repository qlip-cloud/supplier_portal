# -*- coding: utf-8 -*-
"""
seeds.py (documenteme simulation)
================================
Seeds de datos de referencia (Purchase Order, Purchase Receipt, Supplier,
User, sede, reglas) para el escenario simulado. Pueblan el MemoryStore de la
sesion para que approve/assign/reject tengan input real sin tocar la DB.
"""

SIM_NIT = "999999999"

MASTER_SETUP_NAME = "MASTER-SETUP"


def _insert_if_missing(store, doctype, row, name=None):
    """Inserta solo si la fila no existe (seeds idempotentes).

    Los seeds se re-ejecutan en cada resolve() del composition root (p. ej.
    dentro del mismo sync); el insert-replace pisaria el estado mutado de los
    recibos (qp_invoice) o crearia duplicados. Con esta guarda la re-siembra
    es un no-op.
    """
    name = name if name is not None else row.get("name")
    if store.exists(doctype, name):
        return
    store.insert(doctype, row, name=name)


def seed_purchase_order(store, name, headquarter="HQ01", oc_type=None,
                        order_confirmation_no=None):
    _insert_if_missing(store, "qp_SP_PurchaseOrder", {
        "name": name,
        "qp_headquarter": headquarter,
        "qp_oc_type": oc_type,
        "qp_order_confirmation_no": order_confirmation_no or name,
    })


def seed_purchase_receipt(store, name, purchase_order, total,
                          posting_date=None, qp_invoice=None,
                          supplier_delivery_note=None):
    _insert_if_missing(store, "qp_SP_PurchaseReceipt", {
        "name": name,
        "qp_supplier_oc": purchase_order,
        "total": total,
        "posting_date": posting_date or "2026-01-01",
        "qp_invoice": qp_invoice or "",
        "supplier_delivery_note": supplier_delivery_note or name,
    })


def seed_purchase_order_item(store, parent, item_code, qty, unit_cost, uom="UND"):
    _insert_if_missing(store, "qp_SP_PurchaseOrderItem", {
        "name": "{}:{}".format(parent, item_code),
        "parent": parent,
        "parenttype": "Purchase Order",
        "item_code": item_code,
        "uom": uom,
        "qty": qty,
        "qp_unit_cost": unit_cost,
        "qp_extd_cost": (qty or 0) * (unit_cost or 0),
    })


def seed_purchase_receipt_item(store, parent, item_code, qty, rate, uom="UND"):
    _insert_if_missing(store, "qp_SP_PurchaseReceiptItem", {
        "name": "{}:{}".format(parent, item_code),
        "parent": parent,
        "parenttype": "Purchase Receipt",
        "item_code": item_code,
        "uom": uom,
        "qty": qty,
        "rate": rate,
        "amount": (qty or 0) * (rate or 0),
    })


def seed_supplier(store, tax_id, auto_reject=None):
    _insert_if_missing(store, "qp_SP_Supplier", {
        "name": tax_id,
        "tax_id": tax_id,
        "auto_reject": auto_reject,
    })


def seed_user(store, email, full_name=None):
    _insert_if_missing(store, "User", {
        "name": email,
        "email": email,
        "full_name": full_name or email,
        "enabled": 1,
    })


def seed_sede(store, code):
    _insert_if_missing(store, "qp_md_headquarter", {"name": code, "code": code})


def seed_reject_rule(store, name, rule_code, enabled=1, motive="Rechazo"):
    _insert_if_missing(store, "qp_SP_AutoRejectRule", {
        "name": name,
        "rule_name": name,
        "rule_code": rule_code,
        "enabled": enabled,
        "motive": motive,
    })


def seed_master_setup(store, **fields):
    row = dict(fields)
    row["name"] = MASTER_SETUP_NAME
    _insert_if_missing(store, "qp_SP_MasterSetup", row)


def seed_oc_type(store, name, is_inventariable=False):
    _insert_if_missing(store, "qp_SP_OCType", {
        "name": name,
        "oc_type": name,
        "is_inventariable": 1 if is_inventariable else 0,
    })


def seed_assignment_config(store, name, oc_type, headquarter="", user_emails=None):
    """Fila de qp_SP_AssignmentConfig + usuarios destino (child)."""
    _insert_if_missing(store, "qp_SP_AssignmentConfig", {
        "name": name,
        "oc_type": oc_type,
        "headquarter": headquarter,
    })
    for email in (user_emails or []):
        _insert_if_missing(store, "qp_SP_AssignmentConfigUser", {
            "parent": name,
            "parenttype": "qp_SP_AssignmentConfig",
            "user_email": email,
        })


ASSIGNEE_EMAIL = "asignado@sim.local"


def seed_scenario(store):
    """Escenario completo del modo simulador documenteme.

    Siembra la data de referencia que alimenta los 11 fixtures del escenario:
    - 4 facturas de casuistica general (credito/contado, R/A).
    - Banco de recibos: verifica los casos A (consistente -> aprueban todas),
      B (consistencia parcial -> aprueban solo las cubiertas) y C (ninguna
      cubierta -> ninguna aprueba) sobre una OC compartida con varios recibos.
    """
    seed_supplier(store, SIM_NIT)
    seed_master_setup(store, auto_approve=1)
    seed_sede(store, "HQ01")
    seed_oc_type(store, "COMPRA")
    seed_user(store, ASSIGNEE_EMAIL, full_name="Asignado Simulacion")
    seed_assignment_config(
        store, "CFG-COMPRA", oc_type="COMPRA", headquarter="",
        user_emails=[ASSIGNEE_EMAIL],
    )

    seed_purchase_order(store, "PO-SIM-0001", headquarter="HQ01", oc_type="COMPRA")
    seed_purchase_order(store, "PO-A-0001", headquarter="HQ01", oc_type="COMPRA")
    seed_purchase_order(store, "PO-B-0001", headquarter="HQ01", oc_type="COMPRA")
    seed_purchase_order(store, "PO-C-0001", headquarter="HQ01", oc_type="COMPRA")

    seed_purchase_order_item(store, "PO-SIM-0001", "ITEM-0003", 4, 100000)
    seed_purchase_order_item(store, "PO-A-0001", "ITEM-POA1", 1, 2000)
    seed_purchase_order_item(store, "PO-A-0001", "ITEM-POA2", 1, 4000)
    seed_purchase_order_item(store, "PO-B-0001", "ITEM-POB1", 1, 1000)
    seed_purchase_order_item(store, "PO-B-0001", "ITEM-POB2", 1, 2000)
    seed_purchase_order_item(store, "PO-B-0001", "ITEM-POB3", 1, 2500)
    seed_purchase_order_item(store, "PO-C-0001", "ITEM-POC1", 1, 1000)
    seed_purchase_order_item(store, "PO-C-0001", "ITEM-POC2", 1, 800)

    # Caso A: recibos consistentes con ambas facturas (2000 = 500+1500,
    # 4000 = 1000+3000) -> se aprueban todas.
    seed_purchase_receipt(store, "REC-A-1", "PO-A-0001", 500, posting_date="2026-08-20",
                          supplier_delivery_note="RECIBO A1 · 500")
    seed_purchase_receipt(store, "REC-A-2", "PO-A-0001", 1500, posting_date="2026-08-21",
                          supplier_delivery_note="RECIBO A2 · 1500")
    seed_purchase_receipt(store, "REC-A-3", "PO-A-0001", 1000, posting_date="2026-08-22",
                          supplier_delivery_note="RECIBO A3 · 1000")
    seed_purchase_receipt(store, "REC-A-4", "PO-A-0001", 3000, posting_date="2026-08-23",
                          supplier_delivery_note="RECIBO A4 · 3000")

    seed_purchase_receipt_item(store, "REC-A-1", "ITEM-REC-A1", 1, 500)
    seed_purchase_receipt_item(store, "REC-A-2", "ITEM-REC-A2", 1, 1500)
    seed_purchase_receipt_item(store, "REC-A-3", "ITEM-REC-A3", 1, 1000)
    seed_purchase_receipt_item(store, "REC-A-4", "ITEM-REC-A4", 1, 3000)

    # Caso B: cubren 1000 y 2000 pero NO 2500 -> aprueban solo 2 de 3.
    seed_purchase_receipt(store, "REC-B-1", "PO-B-0001", 1000, posting_date="2026-08-20",
                          supplier_delivery_note="RECIBO B1 · 1000")
    seed_purchase_receipt(store, "REC-B-2", "PO-B-0001", 2000, posting_date="2026-08-21",
                          supplier_delivery_note="RECIBO B2 · 2000")
    seed_purchase_receipt(store, "REC-B-3", "PO-B-0001", 1000, posting_date="2026-08-22",
                          supplier_delivery_note="RECIBO B3 · 1000")

    seed_purchase_receipt_item(store, "REC-B-1", "ITEM-REC-B1", 1, 1000)
    seed_purchase_receipt_item(store, "REC-B-2", "ITEM-REC-B2", 1, 2000)
    seed_purchase_receipt_item(store, "REC-B-3", "ITEM-REC-B3", 1, 1000)

    # Caso C: ninguna factura cubre ninguna recepcion -> ninguna aprueba.
    seed_purchase_receipt(store, "REC-C-1", "PO-C-0001", 500, posting_date="2026-08-20",
                          supplier_delivery_note="RECIBO C1 · 500")
    seed_purchase_receipt(store, "REC-C-2", "PO-C-0001", 700, posting_date="2026-08-21",
                          supplier_delivery_note="RECIBO C2 · 700")

    seed_purchase_receipt_item(store, "REC-C-1", "ITEM-REC-C1", 1, 500)
    seed_purchase_receipt_item(store, "REC-C-2", "ITEM-REC-C2", 1, 700)