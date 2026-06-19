import frappe
from qp_supplier_front.www.information.index import get_is_alpla_admin

def get_context(context):

    context.no_cache = 1

    user = frappe.session.user

    user_roles = frappe.get_roles(user)

    context.is_alpla_admin = get_is_alpla_admin(user_roles)

    contact_name = frappe.get_value("Contact", {"user": user}, "name")

    context.user_contact = None
    context.user_suppliers = []

    if contact_name:

        contact = frappe.get_doc("Contact", contact_name)

        context.user_contact = contact

        supplier_links = [link for link in contact.links if link.link_doctype == "Supplier"]

        suppliers = []
        for link in supplier_links:
            try:
                supplier = frappe.get_doc("Supplier", link.link_name)
                suppliers.append(supplier)
            except frappe.DoesNotExistError:
                pass

        context.user_suppliers = suppliers

    error = frappe.request.args.get("error")

    error_messages = {
        "sin_acceso": "No tienes permiso para acceder a este proveedor.",
        "no_encontrado": "El proveedor solicitado no existe."
    }

    context.error_message = error_messages.get(error, "")
