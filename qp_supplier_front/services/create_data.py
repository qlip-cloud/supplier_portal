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
    
    contact = _find_first_contact(supplier, candidate, user)
    
    if contact:
        
        set_contact(doctype, contact, supplier, candidate)
        
        contact.save()
    
    else:
        
        contact = create_contact(supplier, doctype, supplier.supplier_name, candidate, qp_contact_type=None, user=user)
    
    _remove_orphan_contact_duplicates(candidate, contact)
    
    return contact

def _normalize_key(value):
    
    return (value or "").strip().lower()

def _contact_has_email(contact, email_id):
    
    if not email_id:
        
        return False
    
    if _normalize_key(contact.get("email_id")) == _normalize_key(email_id):
        
        return True
    
    return any(
        _normalize_key(row.get("email_id")) == _normalize_key(email_id)
        for row in (contact.get("email_ids") or [])
    )

def _find_supplier_contact_by_email(supplier, email_id):
    
    if not email_id:
        
        return None
    
    for contact in get_dynamic_link(supplier, "Contact"):
        
        if _contact_has_email(contact, email_id):
            
            return contact
    
    return None

def _find_orphan_contact_by_email(email_id):
    
    if not email_id:
        
        return None
    
    rows = frappe.db.sql("""
        SELECT DISTINCT ce.parent
        FROM `tabContact Email` ce
        WHERE LOWER(ce.email_id) = LOWER(%s)
    """, (email_id,), as_dict=False)
    
    for row in rows:
        
        contact = frappe.get_doc("Contact", row[0])
        
        is_linked_to_supplier = any(
            link.get("link_doctype") == "Supplier"
            for link in (contact.get("links") or [])
        )
        
        if not is_linked_to_supplier:
            
            return contact
    
    return None

def _find_first_contact(supplier, candidate, user):
    
    existing = _find_supplier_contact_by_email(supplier, candidate)
    
    if existing:
        
        return existing
    
    if user:
        
        contact_name = frappe.get_value("Contact", filters = {"user": user})
        
        if contact_name:
            
            return frappe.get_doc("Contact", contact_name)
    
    return _find_orphan_contact_by_email(candidate)

def _remove_orphan_contact_duplicates(candidate, kept_contact):
    
    if not candidate:
        
        return
    
    rows = frappe.db.sql("""
        SELECT name
        FROM `tabContact`
        WHERE LOWER(user) = LOWER(%s)
           OR name IN (
               SELECT parent FROM `tabContact Email`
               WHERE LOWER(email_id) = LOWER(%s)
           )
    """, (candidate, candidate), as_dict=False)
    
    for row in rows:
        
        name = row[0]
        
        if name == kept_contact.name:
            
            continue
        
        try:
            
            contact = frappe.get_doc("Contact", name)
            
        except Exception:
            
            continue
        
        if contact.get("links"):
            
            continue
        
        try:
            
            frappe.delete_doc("Contact", name, ignore_permissions=True)
            
        except Exception:
            
            continue

def set_contact(doctype, contact, supplier, email_id, phone = None):
    
    if email_id and not _contact_has_email(contact, email_id):
        
        contact.append("email_ids", {
            "email_id": email_id
        })
    
    if (phone) and not any(
        (row.get("phone") or "").strip() == phone.strip()
        for row in (contact.get("phone_nos") or [])
    ):
        contact.append("phone_nos", {
            "phone": phone
        })
        contact.mobile_no = phone
    
    links = {link.link_doctype + ":" + link.link_name for link in contact.get("links") or []}
    
    if supplier.doctype + ":" + supplier.name not in links:
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