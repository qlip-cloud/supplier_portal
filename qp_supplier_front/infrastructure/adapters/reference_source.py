# -*- coding: utf-8 -*-
"""
reference_source.py (infrastructure - reference data adapter)
=============================================================
Adaptador de referencias de compras para el flujo documenteme: Purchase Order
y Purchase Receipt (+ sus child tables) son consultados a traves de este
contrato, no con doctype hardcodeado en los servicios.

Dos implementaciones:
  - RealReferenceSource: lee frappe (modo real). Replica exactamente las
    consultas que hacia services/enrich_document_detail para no cambiar el
    comportamiento real.
  - MemoryReferenceSource (en simulation/reference_source.py): lee el
    MemoryStore de la sesion (modo simulador).

La vista (services/enrich_document_detail) recibe el adaptador por inyeccion;
si no se inyecta, se resuelve desde el facade de datos (data.references) o se
usa la implementacion real por defecto.
"""


def _frappe():
    import frappe
    return frappe


class RealReferenceSource(object):
    """Referencias de compras (Purchase Order / Purchase Receipt) sobre frappe."""

    def po_exists(self, purchase_order):
        frappe = _frappe()
        if not purchase_order:
            return False
        return bool(frappe.db.exists("Purchase Order", purchase_order))

    def po_items(self, purchase_order):
        frappe = _frappe()
        if not purchase_order:
            return []
        return frappe.get_all(
            "Purchase Order Item",
            filters={
                "parent": purchase_order,
                "parenttype": "Purchase Order",
            },
            fields=["item_code", "uom", "qty", "qp_unit_cost", "qp_extd_cost"],
        )

    def receipts_for(self, purchase_order, qp_invoice=None):
        """Recibos de una OC; si qp_invoice se indica, solo los asignados a esa
        factura (consumidos con nvfac_nume = qp_invoice)."""
        frappe = _frappe()
        if not purchase_order:
            return []
        filters = {"qp_supplier_oc": purchase_order}
        if qp_invoice is not None:
            filters["qp_invoice"] = qp_invoice
        return frappe.get_all(
            "Purchase Receipt",
            filters=filters,
            fields=["name", "supplier_delivery_note", "posting_date", "total"],
        )

    def receipt_bank_for(self, purchase_order):
        from qp_supplier_front.infrastructure.adapters import (
            documenteme_http_adapter,
        )

        return documenteme_http_adapter.get_receipt_bank(purchase_order)

    def receipt_items_for(self, receipt_names):
        frappe = _frappe()
        if not receipt_names:
            return []
        return frappe.get_all(
            "Purchase Receipt Item",
            filters={
                "parent": ["in", receipt_names],
                "parenttype": "Purchase Receipt",
            },
            fields=["item_code", "uom", "qty", "rate", "amount"],
            order_by="parent, idx",
        )