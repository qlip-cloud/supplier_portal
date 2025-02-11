import frappe

def get_home_page(user):    
        
    user_roles = frappe.get_roles(user)
    
    if user == "Administrator" or "Alpla Administrator" in user_roles:
    
        return "/app"
    
    contact_name = frappe.get_value("Contact", {"user": user}, "name")

    if contact_name:
        
        contact = frappe.get_doc("Contact", contact_name)
        
        if contact.links:
            
            supplier = [link for link in contact.links if link.link_doctype == "Supplier"]
            
            if supplier:
                
                return "/information?supplier=" + supplier[0].link_name
    
    return "/information"
    