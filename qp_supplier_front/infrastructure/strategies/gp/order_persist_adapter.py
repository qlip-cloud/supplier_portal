"""
order_persist_adapter.py (GP)
==============================
Adaptador de persistencia para ordenes de compra.
Inserta en tabPurchase Order (padre) y tabPurchase Order Item (hijos)
usando batch insert via raw SQL (misma estrategia que el codigo original).
"""

from qp_supplier_front.util.command import create_doc


def insert_orders(docs, now):
    if not docs:
        return
    table = "`tabPurchase Order`"
    doc_fields = (
        "(name, qp_order_id, qp_create_date, supplier, qp_due_date, "
        "transaction_date, schedule_date, company, creation, modified, "
        "modified_by, owner)"
    )
    create_doc(docs, doc_fields, table)


def insert_order_items(items, now):
    if not items:
        return
    table = "`tabPurchase Order Item`"
    item_fields = (
        "(name, item_code, qp_qty, qty, qp_unit_cost, rate, qp_extd_cost, "
        "parent, parentfield, parenttype, amount, item_name, creation, "
        "modified, modified_by, owner)"
    )
    create_doc(items, item_fields, table)


def insert_errors(errors, now):
    if not errors:
        return
    table = "`tabqp_SP_LineErrorSync`"
    doc_fields = (
        "(name, line, code, error, parent, parentfield, parenttype, "
        "creation, modified, modified_by, owner)"
    )
    create_doc(errors, doc_fields, table)
