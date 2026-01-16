
import frappe
from qp_supplier_front.services.get_data import get_supplier, get_dynamic_link
from qp_supplier_front.services.field_validate import validate_field_list_with_table

def handler(supplier_id, contact_id):
    
    contact = frappe.get_doc("Contact", contact_id)
      
    current_user = frappe.session.user
    if contact.user and contact.user == current_user:
      frappe.throw("No se puede eliminar el contacto asociado al usuario actual.")

      
    contact.delete(ignore_permissions=True)
    frappe.db.commit()

    supplier = get_supplier(supplier_id)
    contacts = get_dynamic_link(supplier, "Contact")

    tables = {
        "email_ids": ["email_id"],
        "phone_nos": ["phone"],
    }
    
    fields_to_validate = ['first_name']
    
    validate_field_list_with_table(supplier, "Contact", "contact", fields_to_validate, tables)

    supplier.save()
      
    list = frappe.render_template("qp_supplier_front/templates/list/information/contacts.html", {
        "contacts": contacts,
        "is_estatus_editable": True
    })
    
    result = {
        "render": {
            "list": list,
            "is_status_editable": True,
            "container": "contact_list",
        }
    }
    
    return result
            