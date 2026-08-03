import frappe
from qp_supplier_front.services.get_data import get_dynamic_link

def create_party(supplier, id_type_name, phone_number, business_type_name, tax_id, email = None):
    
    party = frappe.new_doc("qp_CO_ThirdParty")
    
    set_party(party, supplier, id_type_name, phone_number, business_type_name, tax_id, email)
    
    party.insert()
    
    create_doctype_link(supplier, party)
    
    return party
 
def create_doctype_link(supplier, party):
    
    doctype = "DocType Link"
    
    doctype_link = frappe.new_doc(doctype)
    
    doctype_link.link_fieldname = supplier.name
    doctype_link.link_doctype = supplier.doctype
    doctype_link.parenttype = party.doctype
    doctype_link.parent = party.name
    
    doctype_link.insert()
    
    party.append(doctype, doctype_link)
    
    return doctype_link
    
def set_party(party, supplier, id_type_name, phone_number, business_type_name, tax_id, email = None):
    
    if not party.naming:
        
        party.naming = supplier.tax_id
    
        party.tax_id = supplier.tax_id
        
    party.first_name = supplier.supplier_name
    
    party.id_type = id_type_name
    
    party.phone_number = phone_number
    
    party.email = email
    
    party.business_type = business_type_name
    
def  create_contact(supplier, doctype, first_name,email_id, qp_contact_type=None,phone = None, user = None):
    
    contact = frappe.new_doc(doctype)
    
    contact.first_name = first_name
    
    if user and frappe.db.exists("User", user):
        contact.user = user
    
    contact.qp_contact_type = qp_contact_type
    
    set_contact(doctype, contact, supplier, email_id, phone)
    
    contact.insert()
    
    return contact

def create_first_contact(supplier, email = None):
    
    doctype = "Contact"
    
    candidate = email if email else frappe.session.user
    
    user = candidate if frappe.db.exists("User", candidate) else None
    
    contact_name = frappe.get_value(doctype, filters = {"user": user}) if user else None
    
    if contact_name:
    
        contact = frappe.get_doc(doctype, contact_name)
        
        set_contact(doctype, contact, supplier, candidate)
        
        contact.save()
        
        return contact
        
    contact = create_contact(supplier, doctype, supplier.supplier_name, candidate, qp_contact_type=None, user=user)
    
    return contact

def set_contact(doctype, contact, supplier, email_id, phone = None):
    
    contact.append("email_ids", {
        "email_id": email_id
    })
    
    if (phone):
        contact.append("phone_nos", {
            "phone": phone
        })
        contact.mobile_no = phone
    
    contact.append("links", {
		"link_doctype": supplier.doctype,
		"link_name": supplier.name
	})
    
    if not get_dynamic_link(supplier, doctype):
        
        contact.is_primary_contact = 1

def update_primary_contact_phone(supplier, phone_number):
    if not phone_number:
        return
    filters = [
        ["Dynamic Link", "link_doctype", "=", supplier.doctype],
        ["Dynamic Link", "link_name", "=", supplier.name],
        ["Dynamic Link", "parenttype", "=", "Contact"]
    ]
    contacts = frappe.get_all("Contact", filters=filters, fields=["name", "is_primary_contact"])
    if not contacts:
        return
    target = None
    for c in contacts:
        if c.is_primary_contact:
            target = c
            break
    if not target:
        target = contacts[0]
        for c in contacts:
            if c.name != target.name and c.is_primary_contact:
                frappe.db.set_value("Contact", c.name, "is_primary_contact", 0)
        frappe.db.set_value("Contact", target.name, "is_primary_contact", 1)
    frappe.db.set_value("Contact", target.name, "mobile_no", phone_number)