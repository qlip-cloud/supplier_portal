"""
filter_adapter.py
==================
Adaptador para filtrar registros ya sincronizados en DB.
"""

import frappe
from qp_supplier_front.exception.sync import ExceptionSyncNoNewRecords


def get_last_creation(doctype, supplier_id, order_field):
    latest = frappe.db.get_list(
        doctype,
        filters={"supplier": supplier_id},
        pluck=order_field,
        order_by="{} desc".format(order_field),
        limit=1,
    )
    return latest[0] if latest else None


def get_existing_ids(doctype, id_field, candidate_ids=None):
    if candidate_ids:
        return set(frappe.get_list(
            doctype,
            filters={id_field: ["in", list(candidate_ids)]},
            pluck=id_field,
        ))
    return set(frappe.get_list(doctype, pluck=id_field))

