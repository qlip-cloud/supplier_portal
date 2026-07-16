"""
persist_adapter.py (GP)
========================
Adaptador de persistencia para el flujo GP.
Implementa el contrato definido en domain/ports/persist_orders_port.py.
Utiliza batch insert via raw SQL (misma estrategia que el codigo original).
"""

from qp_supplier_front.util.command import create_doc


def insert_invoices(docs, now):
    if not docs:
        return
    table = "`tabqp_SP_PurchaseInvoice`"
    doc_fields = (
        "(name, invoice_id, status, create_date, registration_date, "
        "currency, subtotal, tax, total, supplier, detail, "
        "qp_sync_flow, creation, modified, modified_by, owner)"
    )
    create_doc(docs, doc_fields, table)


def insert_errors(errors, now):
    if not errors:
        return
    table = "`tabqp_SP_LineErrorSync`"
    doc_fields = (
        "(name, line, code, error, parent, parentfield, parenttype, "
        "creation, modified, modified_by, owner)"
    )
    create_doc(errors, doc_fields, table)

