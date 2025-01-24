import frappe

def daily():
    frappe.get_list("qp_SP_DocumentParty")