# -*- coding: utf-8 -*-
"""
seeds.py (documenteme simulation)
================================
Seeds de datos de referencia (Purchase Order, Purchase Receipt, Supplier,
User, sede, reglas) para el escenario simulado. Pueblan el MemoryStore de la
sesion para que approve/assign/reject tengan input real sin tocar la DB.
"""

SIM_NIT = "999999999"


def seed_purchase_order(store, name, headquarter="HQ01", oc_type=None,
                        order_confirmation_no=None):
    store.insert("qp_SP_PurchaseOrder", {
        "name": name,
        "qp_headquarter": headquarter,
        "qp_oc_type": oc_type,
        "qp_order_confirmation_no": order_confirmation_no or name,
    })


def seed_purchase_receipt(store, name, purchase_order, total):
    store.insert("qp_SP_PurchaseReceipt", {
        "name": name,
        "qp_supplier_oc": purchase_order,
        "total": total,
    })


def seed_supplier(store, tax_id, auto_reject=None):
    store.insert("qp_SP_Supplier", {
        "name": tax_id,
        "tax_id": tax_id,
        "auto_reject": auto_reject,
    })


def seed_user(store, email, full_name=None):
    store.insert("User", {
        "name": email,
        "email": email,
        "full_name": full_name or email,
        "enabled": 1,
    })


def seed_sede(store, code):
    store.insert("qp_md_headquarter", {"name": code, "code": code})


def seed_reject_rule(store, name, rule_code, enabled=1, motive="Rechazo"):
    store.insert("qp_SP_AutoRejectRule", {
        "name": name,
        "rule_name": name,
        "rule_code": rule_code,
        "enabled": enabled,
        "motive": motive,
    })


def seed_master_setup(store, **fields):
    row = dict(fields)
    store.insert("qp_SP_MasterSetup", row)