import frappe


def set_name(doc, method):
    if doc.is_new() and doc.order_confirmation_no:
        doc.name = doc.order_confirmation_no
        doc.qp_order_confirmation_no = doc.order_confirmation_no
        doc.qp_order_id = doc.order_confirmation_no
        doc.flags.name_set = True
