
import frappe

    
def get_contact(contact_id):
    
    contact = frappe.get_doc("Contact", contact_id)
    
    return {
        "contact": contact.as_dict()
    }