# -*- coding: utf-8 -*-
"""
delivery_source.py (infrastructure - delivery configuration adapter)
====================================================================
Lectura de la configuracion de tipos de delivery:

  - qp_SP_DeliveryType: codigos esperados en la OC (name/title/code/description).
  - qp_SP_DeliveryItem: producto BC por tipo, en Supplier (prioridad) y en
    qp_SP_MasterSetup (fallback).

RealDeliverySource lee frappe; MemoryDeliverySource (simulation/) lee el store
de la sesion. El flujo documenteme solo usa esta configuracion en BC.
"""

DELIVERY_TYPE_DOCTYPE = "qp_SP_DeliveryType"
DELIVERY_ITEM_DOCTYPE = "qp_SP_DeliveryItem"
MASTER_SETUP_DOCTYPE = "qp_SP_MasterSetup"
MASTER_SETUP_FIELD = "delivery_items"
SUPPLIER_FIELD = "qp_delivery_items"


class RealDeliverySource(object):
    """Configuracion de delivery sobre frappe (modo real)."""

    def __init__(self, frappe_module=None):
        self._frappe = frappe_module

    def _frappe_module(self):
        if self._frappe is None:
            import frappe
            return frappe
        return self._frappe

    def delivery_types(self):
        """Tipos configurados, tolerando que el doctype aun no este migrado."""
        frappe = self._frappe_module()
        try:
            return frappe.get_all(
                DELIVERY_TYPE_DOCTYPE,
                fields=["name", "title", "code", "description"],
                order_by="name asc",
            )
        except Exception:
            return []

    def master_items(self):
        return self._child_items(MASTER_SETUP_DOCTYPE, MASTER_SETUP_FIELD)

    def supplier_items(self, supplier):
        if not supplier:
            return []
        return self._child_items(supplier, SUPPLIER_FIELD)

    def _child_items(self, parent, parentfield):
        frappe = self._frappe_module()
        try:
            return frappe.get_all(
                DELIVERY_ITEM_DOCTYPE,
                filters={
                    "parent": parent,
                    "parentfield": parentfield,
                },
                fields=["delivery_type", "item_code"],
            )
        except Exception:
            return []


def resolve_delivery_source(data=None, frappe_module=None):
    """Adaptador de config: data.delivery (memoria) o Real por defecto."""
    if data is not None:
        source = getattr(data, "delivery", None)
        if source is not None:
            return source
    return RealDeliverySource(frappe_module=frappe_module)
