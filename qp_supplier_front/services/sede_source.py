# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

"""
sede_source.py
==============
Origen configurable de los datos de sedes para la asignacion automatica
de facturas documenteme.

El doctype fuente se selecciona en `qp_SP_MasterSetup.sede_source_doctype`
(por defecto `qp_md_headquarter`). Se espera que el doctype tenga un campo
`code` con el codigo de la sede (mismo contrato que `qp_md_headquarter`).
"""

import frappe

DEFAULT_SEDE_SOURCE = "qp_md_headquarter"

MASTER_SETUP_DOCTYPE = "qp_SP_MasterSetup"
SEDE_SOURCE_FIELD = "sede_source_doctype"


def get_sede_source_doctype():
    source = frappe.db.get_single_value(MASTER_SETUP_DOCTYPE, SEDE_SOURCE_FIELD)
    return source or DEFAULT_SEDE_SOURCE


def sede_exists(sede_code):
    if not sede_code:
        return False

    doctype = get_sede_source_doctype()
    if not doctype or not frappe.db.exists("DocType", doctype):
        return False

    if frappe.db.exists(doctype, {"code": sede_code}):
        return True

    return bool(frappe.db.exists(doctype, sede_code))


def list_sedes():
    """Lista las sedes del doctype fuente configurado.

    Devuelve registros con 'code' y 'title'. Si el doctype fuente no existe
    o no esta configurado, retorna una lista vacia.
    """
    doctype = get_sede_source_doctype()
    if not doctype or not frappe.db.exists("DocType", doctype):
        return []

    return frappe.get_all(
        doctype,
        fields=["code", "title"],
        order_by="title asc",
    )
