"""
order_strategy.py (GP)
=======================
Estrategia GP para sincronizacion de ordenes de compra.
Define endpoints, transformacion y persistencia especificos.
Las ordenes solo existen en el flujo GP (no hay BC).
"""

from qp_supplier_front.constant.endpoint import (
    ORDER_SUPPLIER_ID,
    ORDER_SUPPLIER_DATE_RANGE,
)
from qp_supplier_front.infrastructure.strategies.gp.order_transform import (
    build_order_records,
)
from qp_supplier_front.infrastructure.strategies.gp.order_persist_adapter import (
    insert_orders,
    insert_order_items,
    insert_errors,
)


def build_order_param(supplier_id, window_start, window_end):
    return "{}/{}/{}".format(supplier_id, str(window_start), str(window_end))


ORDER_STRATEGY = {
    "name": "GP",
    "endpoints": {
        "per_supplier": ORDER_SUPPLIER_ID,
        "per_supplier_range": ORDER_SUPPLIER_DATE_RANGE,
    },
    "db_fields": {
        "id_field": "qp_order_id",
        "order_field": "qp_create_date",
        "supplier_field": "supplier",
    },
    "doctype": "Purchase Order",
    "request_key": "orders",
    "request_key_id": "orderId",
    "request_list_key": "products",
    "request_list_key_id": "itemnmbr",
    "build_param": build_order_param,
    "transform": build_order_records,
    "persist": {
        "insert_orders": insert_orders,
        "insert_items": insert_order_items,
        "insert_errors": insert_errors,
    },
}
