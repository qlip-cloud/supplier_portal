"""
strategy.py (BC)
==================
Definicion de la estrategia BC (nuevo flujo).
Reusa el persist adapter de GP porque persiste en el mismo doctype.
"""

from qp_supplier_front.infrastructure.strategies.bc.transform import (
    build_invoices,
    filter_invoices,
)
from qp_supplier_front.infrastructure.strategies.gp.persist_adapter import (
    insert_invoices,
    insert_errors,
)


def build_bc_param(supplier_id, last_date=None, now=None):
    if last_date:
        return "$filter=Vendor_No eq '{}' and Document_Type eq 'Invoice' and Posting_Date ge {} and Posting_Date le {}".format(
            supplier_id, last_date, now
        )
    return "$filter=Vendor_No eq '{}' and Document_Type eq 'Invoice'".format(supplier_id)


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
    "filter": filter_invoices,
    "build_param": build_bc_param,
    "persist": {
        "insert_invoices": insert_invoices,
        "insert_errors": insert_errors,
    },
}

