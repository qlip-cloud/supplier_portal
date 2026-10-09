"""
sync_checkpoint.py
==================
Helpers compartidos para el sync de recibos/facturas POR PROVEEDOR con
checkpoint en Supplier (qp_<tipo>_last_sync) y fecha inicial global
configurable en qp_SP_MasterSetup.initial_sync_date (default 2024-01-01).

Permite:
  - get_initial_sync_date(): fecha inicial global.
  - get_checkpoint / set_checkpoint: leer/actualizar la ultima sincronizacion
    del proveedor (solo se actualiza cuando el sync del proveedor termina ok).
  - suppliers_without_checkpoint / suppliers_with_checkpoint: seleccion para
    sync_full (pendientes) y sync_incremental (ya inicializados).
"""

from datetime import datetime

import frappe

from qp_supplier_front.services.sync_window import coerce_datetime

DEFAULT_INITIAL_DATE = datetime(2024, 1, 1)


def get_initial_sync_date():
    try:
        value = frappe.db.get_single_value(
            "qp_SP_MasterSetup", "initial_sync_date"
        )
    except Exception:
        value = None
    parsed = coerce_datetime(value) if value else None
    return parsed or DEFAULT_INITIAL_DATE


def get_checkpoint(supplier_id, field):
    try:
        return frappe.db.get_value("Supplier", supplier_id, field)
    except Exception:
        return None


def set_checkpoint(supplier_id, field, when):
    try:
        frappe.db.set_value("Supplier", supplier_id, field, when)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Error al guardar checkpoint de sincronizacion",
        )


def suppliers_without_checkpoint(field):
    return frappe.db.sql_list(
        "select name from `tabSupplier` where ifnull(`{f}`, '') = ''".format(
            f=field
        )
    )


def suppliers_with_checkpoint(field):
    return frappe.db.sql_list(
        (
            "select name from `tabSupplier` "
            "where `{f}` is not null and `{f}` <> ''"
        ).format(f=field)
    )