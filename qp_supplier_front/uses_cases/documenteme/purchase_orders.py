# -*- coding: utf-8 -*-
"""
purchase_orders.py (documenteme)
================================
Nucleo puro para interpretar el campo `nvfac_orde` cuando documenteme envia
varias ordenes de compra en un mismo documento separadas por coma.

No importa Frappe. Las funciones son puras y tolerantes a valores vacios,
espacios sobrantes, comas repetidas y ordenes duplicadas.
"""


def parse_purchase_orders(value):
    """Lista de OC depurada (orden de aparicion, sin vacios ni duplicados).

    Acepta el string original de `nvfac_orde` (p. ej. "OC1, OC2"), una lista
    ya separada o None. Cada token se limpia (strip) antes de validarse.
    """
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_tokens = list(value)
    else:
        raw_tokens = str(value).split(",")

    orders = []
    for token in raw_tokens:
        cleaned = str(token or "").strip()
        if cleaned and cleaned not in orders:
            orders.append(cleaned)
    return orders


def is_multiple_purchase_orders(value):
    """True si el documento trae mas de una OC."""
    return len(parse_purchase_orders(value)) > 1


def single_purchase_order(value):
    """La OC unica o vacio cuando no hay ninguna o hay varias."""
    orders = parse_purchase_orders(value)
    if len(orders) == 1:
        return orders[0]
    return ""


def header_purchase_order(value):
    """Valor de cabecera para campos escalares (NoPedidoProveedor/numeroPord).

    Con varias OC se envia vacio (el detalle de cada linea conserva su propia
    recepcion y OC).
    """
    return single_purchase_order(value)


def first_purchase_order(value):
    """Primera OC (util para datos de cabecera como fechas de la OC)."""
    orders = parse_purchase_orders(value)
    return orders[0] if orders else ""
