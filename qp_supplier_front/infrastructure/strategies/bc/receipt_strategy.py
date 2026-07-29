"""
receipt_strategy.py (BC)
=========================
Estrategia BC para recibos de pago.
Usa endpoint list_payment_receipt de BC via OAuth2.
Agrupa lineas por Document_No_Pago: 1 padre + N hijos
(qp_SP_PaymentReceiptItem) con datos de facturas asociadas.
Reusa persist adapter de GP (mismo doctype).
"""

from qp_supplier_front.infrastructure.strategies.bc.receipt_transform import (
    build_payments,
)
from qp_supplier_front.infrastructure.strategies.gp.receipt_persist_adapter import (
    insert_payments,
    insert_payment_items,
    insert_errors,
)


def build_bc_param(supplier_id, last_date=None, now=None):
    if last_date:
        return "$filter=Vendor_No_ eq '{}' and Posting_Date ge {} and Posting_Date le {}".format(
            supplier_id, last_date, now
        )
    return "$filter=Vendor_No_ eq '{}'".format(supplier_id)


BC_RECEIPT_STRATEGY = {
    "name": "BC",
    "endpoints": {
        "per_supplier": "list_payment_receipt",
        "per_supplier_range": "list_payment_receipt",
        "all": "list_payment_receipt",
    },
    "db_fields": {
        "id_field": "qp_receipt_id",
        "order_field": "qp_posting_date",
        "supplier_field": "supplier",
        "sync_flow_field": "qp_sync_flow",
    },
    "request_list_key": None,
    "doctype": "qp_SP_PaymentReceipt",
    "request_key": "value",
    "request_key_id": "Document_No_Pago",
    "transform": build_payments,
    "build_param": build_bc_param,
    "persist": {
        "insert_payments": insert_payments,
        "insert_items": insert_payment_items,
        "insert_errors": insert_errors,
    },
}
