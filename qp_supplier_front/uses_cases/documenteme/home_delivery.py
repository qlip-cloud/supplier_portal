# -*- coding: utf-8 -*-
"""
home_delivery.py (documenteme)
==============================
Nucleo puro de las facturas de HOME DELIVERY.

Una factura de home delivery llega sin orden de compra ni recepcion reales:
el campo `nvfac_orde` trae el marcador textual `entregapaciente009`. Como no
hay productos homologados, la factura se envia a BC con UNA sola linea usando
el producto configurado en `qp_SP_MasterSetup.home_delivery_item`; se acumulan
la cantidad y el subtotal de todas las lineas de la factura.

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


def is_home_delivery(doc):
    """True si el campo OC de la factura trae el marcador de home delivery.

    La comparacion es tolerante a mayusculas y espacios: se busca el marcador
    dentro del texto del campo `nvfac_orde`.
    """
    value = (doc or {}).get("nvfac_orde") or ""
    return HOME_DELIVERY_MARK in str(value).strip().lower()


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
