"""
sync_invoices.py - SHIM
========================
Composition Root legacy de sincronizacion de facturas de compra.
Re-exporta desde el nuevo modulo uses_cases/purchase_invoice/sync_by_supplier.py
para usar el flujo fraccionado por ventanas (con log y lock).

Eliminar este archivo cuando todos los entry points apunten al nuevo modulo.
"""

from qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier import (  # noqa
    sync_by_supplier,
    sync_all,
)
