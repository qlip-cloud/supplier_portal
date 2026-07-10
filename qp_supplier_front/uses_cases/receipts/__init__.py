import frappe


def set_name(doc, method):
    if doc.is_new() and doc.qp_supplier_delivery_note:
        doc.name = doc.qp_supplier_delivery_note
