"""
receipt_persist_adapter.py (GP)
================================
Adaptador de persistencia para recibos de pago.
Inserta en tabqp_SP_PaymentReceipt (padre) y opcionalmente
en tabqp_SP_PaymentReceiptItem (hijos).
"""

from qp_supplier_front.util.command import create_doc


def insert_payments(docs, now):
    if not docs:
        return
    table = "`tabqp_SP_PaymentReceipt`"
    doc_fields = (
        "(name, qp_receipt_id, supplier, qp_supplier_name, "
        "qp_posting_date, qp_amount, qp_description, "
        "qp_sync_flow, qp_external_document_no, qp_payment_type, "
        "creation, modified, modified_by, owner)"
    )
    create_doc(docs, doc_fields, table)


def insert_payment_items(items, now):
    if not items:
        return
    table = "`tabqp_SP_PaymentReceiptItem`"
    item_fields = (
        "(name, qp_document_no_factura, qp_sequence, qp_amount, "
        "qp_external_document_no, parent, parentfield, parenttype, "
        "creation, modified, modified_by, owner)"
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
