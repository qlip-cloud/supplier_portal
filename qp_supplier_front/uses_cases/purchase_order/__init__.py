import frappe


def set_name(doc, method):
    if doc.is_new() and doc.order_confirmation_no:
        doc.name = doc.order_confirmation_no
