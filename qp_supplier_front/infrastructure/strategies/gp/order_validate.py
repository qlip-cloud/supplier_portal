"""
order_validate.py (GP)
======================
Validaciones de ordenes de compra extraidas de
uses_cases/sales_order/sync_by_supplier.py.
"""

from qp_supplier_front.exception.sync import (
    ExceptionAmountMaxLengthNotValid,
)


def assert_amount_max_length_valid(amount, item_code, order):
    if len(amount) > 18:
        raise ExceptionAmountMaxLengthNotValid(amount, item_code, order)
