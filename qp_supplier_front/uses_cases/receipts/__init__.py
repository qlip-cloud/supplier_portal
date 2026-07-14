import frappe


def set_name(doc, method):
    if doc.is_new() and doc.supplier_delivery_note:
        doc.name = doc.supplier_delivery_note
        doc.qp_supplier_delivery_note = doc.supplier_delivery_note
