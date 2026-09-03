"""
sync_by_supplier.py (receipts) - SHIM
======================================
Re-exporta desde uses_cases.payment_receipt para compatibilidad
con referencias legacy (www, taks, services).
"""

from qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier import (  # noqa
    sync_by_supplier,
    sync_all,
)

handler = sync_by_supplier
handler_all = sync_all
