# -*- coding: utf-8 -*-
"""
add_delivery_type_config.py
===========================
Configuracion inicial de tipos de delivery.

  - Crea (si no existen) los tipos home_delivery e internal_delivery con sus
    codigos esperados en la OC.
  - No toca la configuracion de proveedores.

Idempotente.
"""

import frappe

DELIVERY_TYPE_DOCTYPE = "qp_SP_DeliveryType"

DEFAULT_TYPES = (
    {
        "name": "home_delivery",
        "title": "Home delivery",
        "code": "entregapaciente009",
        "description": "Factura de home delivery",
    },
    {
        "name": "internal_delivery",
        "title": "Internal delivery",
        "code": "entregainterna009",
        "description": "Factura de internal delivery",
    },
)


def execute():
    if not frappe.db.exists("DocType", DELIVERY_TYPE_DOCTYPE):
        return

    for delivery_type in DEFAULT_TYPES:
        if frappe.db.exists(DELIVERY_TYPE_DOCTYPE, delivery_type["name"]):
            continue
        doc = frappe.get_doc(dict(delivery_type, doctype=DELIVERY_TYPE_DOCTYPE))
        doc.insert(ignore_permissions=True)
