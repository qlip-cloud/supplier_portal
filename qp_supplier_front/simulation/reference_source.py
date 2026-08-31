# -*- coding: utf-8 -*-
"""
reference_source.py (documenteme simulation)
============================================
Implementacion in-memory del contrato de referencias de compras (
infrastructure/adapters/reference_source.RealReferenceSource) sobre el
MemoryStore de la sesion.

Reemplaza el doctype hardcodeado por el adaptador que inyecta la vista en modo
simulador: Purchase Order / Purchase Receipt (+ child tables) se leen de las
tablas en memoria (qp_SP_PurchaseOrder / qp_SP_PurchaseReceipt /
qp_SP_PurchaseOrderItem / qp_SP_PurchaseReceiptItem) sembradas por los seeds.
"""

from qp_supplier_front.simulation import references_memory


class MemoryReferenceSource(object):

    def __init__(self, store):
        self._store = store

    def po_exists(self, purchase_order):
        return references_memory.memory_po_exists(self._store, purchase_order)

    def po_items(self, purchase_order):
        store = self._store
        if not purchase_order:
            return []
        return store.query(
            "qp_SP_PurchaseOrderItem",
            filters={
                "parent": purchase_order,
                "parenttype": "Purchase Order",
            },
            fields=["item_code", "uom", "qty", "qp_unit_cost", "qp_extd_cost"],
        )

    def receipts_for(self, purchase_order, qp_invoice=None):
        store = self._store
        if not purchase_order:
            return []
        filters = {"qp_supplier_oc": purchase_order}
        if qp_invoice is not None:
            filters["qp_invoice"] = qp_invoice
        return store.query(
            "qp_SP_PurchaseReceipt",
            filters=filters,
            fields=["name", "supplier_delivery_note", "posting_date", "total"],
        )

    def receipt_bank_for(self, purchase_order):
        return references_memory.memory_get_receipt_bank(
            self._store, purchase_order)

    def receipt_items_for(self, receipt_names):
        store = self._store
        if not receipt_names:
            return []
        return store.query(
            "qp_SP_PurchaseReceiptItem",
            filters={
                "parent": ["in", receipt_names],
                "parenttype": "Purchase Receipt",
            },
            fields=["item_code", "uom", "qty", "rate", "amount"],
            order_by="parent, idx",
        )