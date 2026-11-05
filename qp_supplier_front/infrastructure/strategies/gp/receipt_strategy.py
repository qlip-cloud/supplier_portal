"""
receipt_strategy.py (GP)
=========================
Estrategia GP para recibos de pago.
Endpoints, transformacion y persistencia especificos de GP.
"""

from qp_supplier_front.constant.endpoint import (
    PAYMENT_SUPPLIER_ID,
    PAYMENT_SUPPLIER_DATE_RANGE,
    PAYMENT_ALL,
)
from qp_supplier_front.infrastructure.strategies.gp.receipt_transform import (
    build_payments,
)
from qp_supplier_front.infrastructure.strategies.gp.receipt_persist_adapter import (
    insert_payments,
    insert_payment_items,
    insert_errors,
)


def build_gp_param(supplier_id, last_date=None, now=None):
    if last_date:
        return "{}/{}/{}".format(supplier_id, last_date, now)
    return str(supplier_id)


GP_RECEIPT_STRATEGY = {
    "name": "GP",
    "endpoints": {
        "per_supplier": PAYMENT_SUPPLIER_ID,
        "per_supplier_range": PAYMENT_SUPPLIER_DATE_RANGE,
        "all": PAYMENT_ALL,
    },
    "db_fields": {
        "id_field": "qp_receipt_id",
        "order_field": "qp_posting_date",
        "supplier_field": "supplier",
        "sync_flow_field": "qp_sync_flow",
    },
    "request_list_key": "reference",
    "doctype": "qp_SP_PaymentReceipt",
    "request_key": "payments",
    "request_key_id": "vchrnmbr",
    "transform": build_payments,
    "build_param": build_gp_param,
    "persist": {
        "insert_payments": insert_payments,
        "insert_items": insert_payment_items,
        "insert_errors": insert_errors,
    },
}
