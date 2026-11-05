"""
strategy.py (GP)
==================
Definicion de la estrategia GP (flujo actual).
Contiene las configuraciones especificas del flujo:
  - Endpoints de API
  - Nombres de campos en DB
  - Campo de ordenamiento
  - Callbacks de transformacion y persistencia
"""
from qp_supplier_front.constant.endpoint import (
    INVOICE_SUPPLIER_ID,
    INVOICE_SUPPLIER_DATE_RANGE,
    INVOICE_ALL,
)
from qp_supplier_front.infrastructure.strategies.gp.transform import (
    build_invoices,
    filter_invoices,
)
from qp_supplier_front.infrastructure.strategies.gp.persist_adapter import (
    insert_invoices,
    insert_errors,
)


def build_gp_param(supplier_id, last_date=None, now=None):
    if last_date:
        return "{}/{}/{}".format(supplier_id, last_date, now)
    return str(supplier_id)


GP_STRATEGY = {
    "name": "GP",
    "endpoints": {
        "per_supplier": INVOICE_SUPPLIER_ID,
        "per_supplier_range": INVOICE_SUPPLIER_DATE_RANGE,
        "all": INVOICE_ALL,
    },
    "db_fields": {
        "id_field": "invoice_id",
        "order_field": "create_date",
        "supplier_field": "supplier",
        "sync_flow_field": "qp_sync_flow",
    },
    "doctype": "qp_SP_PurchaseInvoice",
    "request_key": "invoices",
    "request_key_id": "invoiceId",
    "transform": build_invoices,
    "filter": filter_invoices,
    "build_param": build_gp_param,
    "persist": {
        "insert_invoices": insert_invoices,
        "insert_errors": insert_errors,
    },
}

