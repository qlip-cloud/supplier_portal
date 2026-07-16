"""
strategy.py (BC)
==================
Definicion de la estrategia BC (nuevo flujo).
Reusa el persist adapter de GP porque persiste en el mismo doctype.
"""

from qp_supplier_front.infrastructure.strategies.bc.transform import (
    build_invoices,
)
from qp_supplier_front.infrastructure.strategies.gp.persist_adapter import (
    insert_invoices,
    insert_errors,
)


BC_STRATEGY = {
    "name": "BC",
    "endpoints": {
        "per_supplier": "list_purchase_invoice",
        "per_supplier_range": "list_purchase_invoice",
        "all": "list_purchase_invoice",
    },
    "db_fields": {
        "id_field": "invoice_id",
        "order_field": "create_date",
        "supplier_field": "supplier",
        "sync_flow_field": "qp_sync_flow",
    },
    "doctype": "qp_SP_PurchaseInvoice",
    "request_key": "value",
    "request_key_id": "Document_No",
    "transform": build_invoices,
    "persist": {
        "insert_invoices": insert_invoices,
        "insert_errors": insert_errors,
    },
}

