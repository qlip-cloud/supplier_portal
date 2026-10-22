# -*- coding: utf-8 -*-
"""
home_delivery.py (documenteme)
==============================
Nucleo puro de las facturas de HOME DELIVERY.

Una factura de delivery llega sin orden de compra ni recepcion reales: el
campo `nvfac_orde` trae un codigo configurado en `qp_SP_DeliveryType`
(por ejemplo `entregapaciente009`). Como no hay productos homologados, la
factura se envia a BC con UNA sola linea usando el producto configurado en
el proveedor o, en su defecto, en `qp_SP_MasterSetup.delivery_items`; se
acumulan la cantidad y el subtotal de todas las lineas de la factura.

Sin imports a Frappe: las funciones son puras y reutilizables por el flujo
real y por la simulacion.
"""

HOME_DELIVERY_MARK = "entregapaciente009"
HOME_DELIVERY_COMMENT = "Factura de home delivery"


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_code(value):
    return str(value or "").strip().lower()


def is_home_delivery(doc):
    """True si el campo OC de la factura trae el marcador de home delivery.

    La comparacion es tolerante a mayusculas y espacios: se busca el marcador
    dentro del texto del campo `nvfac_orde`.

    Se conserva como respaldo/compatibilidad; el flujo actual usa
    `find_delivery_type` con los codigos configurados en qp_SP_DeliveryType.
    """
    value = (doc or {}).get("nvfac_orde") or ""
    return HOME_DELIVERY_MARK in _normalize_code(value)


def find_delivery_type(order_value, delivery_types):
    """Tipo de delivery configurado cuyo `code` aparece en la OC.

    La comparacion es tolerante a mayusculas/espacios y por coincidencia
    parcial (el `code` puede venir dentro del texto de `nvfac_orde`). Retorna
    el dict del tipo (name/title/code/description) o None.
    """
    order = _normalize_code(order_value)
    if not order:
        return None
    for delivery_type in delivery_types or []:
        code = _normalize_code((delivery_type or {}).get("code"))
        if code and code in order:
            return delivery_type
    return None


def _first_item_for_type(delivery_type_name, items):
    for item in items or []:
        row = item or {}
        if row.get("delivery_type") == delivery_type_name:
            item_code = row.get("item_code")
            if item_code:
                return item_code
    return ""


def resolve_delivery_item(delivery_type, supplier_items, master_items):
    """Producto del tipo de delivery: primero proveedor, luego MasterSetup.

    Retorna "" si ninguna de las dos tablas tiene configurado el producto.
    """
    delivery_type_name = (delivery_type or {}).get("name")
    if not delivery_type_name:
        return ""
    return (
        _first_item_for_type(delivery_type_name, supplier_items)
        or _first_item_for_type(delivery_type_name, master_items)
    )


def get_delivery_comment(delivery_type):
    """Comentario BC configurado en el tipo de delivery (o "")."""
    return str((delivery_type or {}).get("description") or "").strip()


def resolve_delivery(doc, delivery_types, supplier_items, master_items):
    """Contexto de delivery de una factura (o None si no es delivery).

    Retorna {"delivery_type", "item_code", "comment"} cuando el campo OC de la
    factura coincide con algun codigo configurado.
    """
    delivery_type = find_delivery_type(
        (doc or {}).get("nvfac_orde"), delivery_types
    )
    if delivery_type is None:
        return None
    return {
        "delivery_type": delivery_type,
        "item_code": resolve_delivery_item(
            delivery_type, supplier_items, master_items
        ),
        "comment": get_delivery_comment(delivery_type),
    }


def build_home_delivery_line(detail_lines, item_code):
    """Linea unica consolidada para una factura de home delivery.

    Acumula la cantidad (`nvdet_tcan`) y el subtotal (`nvdet_stot`, con
    fallback a cantidad * valor unitario) de todas las lineas de la factura.
    El precio unitario se deriva del subtotal acumulado entre la cantidad.

    Retorna None si no hay producto configurado o si la factura no tiene
    lineas de detalle.
    """
    if not item_code:
        return None
    lines = detail_lines or []
    if not lines:
        return None

    qty = 0.0
    subtotal = 0.0
    for line in lines:
        line_qty = _as_float(line.get("nvdet_tcan"))
        raw_subtotal = line.get("nvdet_stot")
        line_subtotal = (
            _as_float(raw_subtotal)
            if raw_subtotal is not None
            else line_qty * _as_float(line.get("nvdet_valo"))
        )
        qty += line_qty
        subtotal += line_subtotal

    if not qty and not subtotal:
        return None
    effective_qty = qty or 1.0
    return {
        "item_code": item_code,
        "qty": effective_qty,
        "rate": subtotal / effective_qty,
        "idx": 0,
        "uom": "",
        "receiving_no": "",
        "order_no": "",
    }
