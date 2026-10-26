import frappe
from qp_supplier_front.www.information.index import get_is_alpla_admin
from qp_supplier_front.services.get_data import get_party, get_dynamic_link

def get_context(context):

    context.no_cache = 1

    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    context.is_alpla_admin = get_is_alpla_admin(user_roles)

    suppliers = []

    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")

    if contact_name:
        contact = frappe.get_doc("Contact", contact_name)

        if contact.links:
            for link in contact.links:
                try:
                    if link.link_doctype != "Supplier":
                        continue

                    supplier = frappe.get_doc("Supplier", link.link_name)
                    party = get_party(supplier)

                    addresses = get_dynamic_link(supplier, "Address")
                    address = addresses[0] if addresses else None

                    phone = supplier.get("mobile_no") or supplier.get("phone_no") or ""

                    tax_id = party.get("tax_id") if party else ""
                    id_type = party.get("id_type") if party else ""
                    dni = (id_type + " " + tax_id) if id_type and tax_id else (tax_id or "")

                    addr = address.get("address_line1") or "" if address else ""

                    suppliers.append({
                        "name": supplier.get("name"),
                        "supplier_name": supplier.get("supplier_name"),
                        "qp_status": supplier.get("qp_status"),
                        "dni": dni,
                        "address": addr,
                        "phone": phone,
                    })
                except Exception:
                    continue

    context.user_suppliers = suppliers

    error = frappe.request.args.get("error")
    error_messages = {
        "sin_acceso": "No tienes permiso para acceder a este proveedor.",
        "no_encontrado": "El proveedor solicitado no existe."
    }
    context.error_message = error_messages.get(error, "")

    context.status_classes = {
        "En proceso": "badge-info",
        "Aprobado": "badge-success",
        "En revisión": "badge-warning",
        "Rechazado": "badge-danger",
    }
