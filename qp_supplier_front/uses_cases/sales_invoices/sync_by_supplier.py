"""
sync_by_supplier.py (sales_invoices)
=====================================
Shim de compatibilidad hacia atras.
Re-exporta desde el nuevo modulo uses_cases/purchase_invoice/.
Mantiene los alias handler() y handler_all() para no romper
referencias existentes en:
  - taks/sync.py
  - www/purchase_invoices/index.py
  - resources/utils/pagination.py (import dinamico via key)

Eliminar este archivo cuando todos los entry points se actualicen
a usar resources/api/sync_invoices.py directamente.
"""

from qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier import (
    sync_by_supplier,
    sync_all,
)

handler = sync_by_supplier
handler_all = sync_all

