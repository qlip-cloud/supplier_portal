"""
sync_by_supplier.py (sales_order) - SHIM
=========================================
Re-exporta desde el nuevo modulo uses_cases/purchase_order/ para no romper
referencias dinamicas existentes:
  - resources/utils/pagination.py (import dinamico via key)
  - www/purchase_order/index.py

Eliminar este archivo cuando todos los entry points apunten al nuevo modulo.
"""

from qp_supplier_front.uses_cases.purchase_order.sync_by_supplier import (  # noqa
    sync_by_supplier,
)

handler = sync_by_supplier
