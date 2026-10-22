# -*- coding: utf-8 -*-
"""
add_delivery_type_config.py
===========================
Configuracion inicial de tipos de delivery y migracion del campo legado
`qp_SP_MasterSetup.home_delivery_item`.

  - Crea (si no existen) los tipos home_delivery e internal_delivery con sus
    codigos esperados en la OC.
  - Si la tabla nueva del MasterSetup no tiene configurado home_delivery y el
    campo legado tiene producto, lo copia para conservar el comportamiento
    existente.
  - No toca la configuracion de proveedores.

Idempotente.
"""

import frappe

DELIVERY_TYPE_DOCTYPE = "qp_SP_DeliveryType"
MASTER_SETUP_DOCTYPE = "qp_SP_MasterSetup"
MASTER_SETUP_FIELD = "delivery_items"

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

    _migrate_legacy_home_delivery_item()


def _migrate_legacy_home_delivery_item():
    if not frappe.db.exists("DocType", MASTER_SETUP_DOCTYPE):
        return
    if not frappe.get_meta(MASTER_SETUP_DOCTYPE).has_field(MASTER_SETUP_FIELD):
        return

    legacy_item = frappe.db.get_single_value(
        MASTER_SETUP_DOCTYPE, "home_delivery_item"
    )
    if not legacy_item:
        return

    master_setup = frappe.get_single(MASTER_SETUP_DOCTYPE)
    configured = [
        row.get("delivery_type") for row in (master_setup.get(MASTER_SETUP_FIELD) or [])
    ]
    if "home_delivery" in configured:
        return

    master_setup.append(MASTER_SETUP_FIELD, {
        "delivery_type": "home_delivery",
        "item_code": legacy_item,
    })
    master_setup.save(ignore_permissions=True)
