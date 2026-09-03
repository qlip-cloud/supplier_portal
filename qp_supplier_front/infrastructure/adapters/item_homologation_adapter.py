# -*- coding: utf-8 -*-
"""
item_homologation_adapter.py
============================
Adaptador de infraestructura para la homologacion de codigos de producto
proveedor -> BC (tabla qp_SP_ItemHomologation).

Sirve al flujo de aprobacion documenteme cuando una factura no tiene recibo
de compra (por lo general facturas de contado): se toman las lineas de la
factura del proveedor (qp_SP_DetailLine) y se mapea el codigo del proveedor
(nvpro_codi) al codigo BC (bc_item_code) usando la tabla de homologacion.

Sigue la regla de lazy imports: frappe se importa dentro de cada funcion para
que este modulo se pueda importar sin Frappe instalado.
"""


def resolve_supplier(tax_id, frappe_module=None):
    """Resuelve el nombre del proveedor (Supplier) dado su tax_id.

    Usa la misma logica que resources/documenteme/_approve_base
    (get_supplier_by_tax_id): el NIT de la factura (nvpro_ndoc/tax_id).
    Retorna None si no se encuentra proveedor.
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not tax_id:
        return None

    suppliers = frappe_module.get_all(
        "Supplier",
        filters={"tax_id": tax_id},
        pluck="name",
        limit=1,
    )
    return suppliers[0] if suppliers else None


def get_homologation_map(supplier, frappe_module=None):
    """Retorna {supplier_item_code: bc_item_code} para un proveedor.

    Solo considera registros activos (active=1). Si el proveedor no existe
    retorna un dict vacio.
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not supplier:
        return {}

    rows = frappe_module.get_all(
        "qp_SP_ItemHomologation",
        filters={"supplier": supplier, "active": 1},
        fields=["supplier_item_code", "bc_item_code"],
    )
    return {
        row.get("supplier_item_code"): row.get("bc_item_code")
        for row in rows
        if row.get("supplier_item_code")
    }


def get_invoice_detail_lines(document_name, frappe_module=None):
    """Retorna las lineas de detalle de la factura del proveedor.

    Devuelve una lista de dicts con los campos minimos que consume la
    homologacion: nvpro_codi, nvuni_desc, nvdet_tcan, nvdet_valo.
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not document_name:
        return []

    return frappe_module.get_all(
        "qp_SP_DetailLine",
        filters={"parent": document_name, "parenttype": "qp_SP_DocumentDetail"},
        fields=["nvpro_codi", "nvuni_desc", "nvdet_tcan", "nvdet_valo"],
        order_by="idx",
    )
