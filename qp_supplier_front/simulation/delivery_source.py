# -*- coding: utf-8 -*-
"""
delivery_source.py (documenteme simulation)
===========================================
Implementacion in-memory de la configuracion de tipos de delivery.

Lee SOLO del MemoryStore de la sesion: tipos (qp_SP_DeliveryType) y productos
por tipo (qp_SP_DeliveryItem) del proveedor y de qp_SP_MasterSetup. NUNCA
consulta frappe.
"""

from qp_supplier_front.infrastructure.adapters.delivery_source import (
    DELIVERY_ITEM_DOCTYPE,
    DELIVERY_TYPE_DOCTYPE,
    MASTER_SETUP_DOCTYPE,
    MASTER_SETUP_FIELD,
    SUPPLIER_FIELD,
)


class MemoryDeliverySource(object):

    def __init__(self, store):
        self._store = store

    def delivery_types(self):
        return self._store.query(
            DELIVERY_TYPE_DOCTYPE,
            fields=["name", "title", "code", "description"],
            order_by="name asc",
        )

    def master_items(self):
        return self._child_items(MASTER_SETUP_DOCTYPE, MASTER_SETUP_FIELD)

    def supplier_items(self, supplier):
        if not supplier:
            return []
        return self._child_items(supplier, SUPPLIER_FIELD)

    def _child_items(self, parent, parentfield):
        return self._store.query(
            DELIVERY_ITEM_DOCTYPE,
            filters={"parent": parent, "parentfield": parentfield},
            fields=["delivery_type", "item_code"],
        )
