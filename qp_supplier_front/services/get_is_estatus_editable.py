import frappe

def handler(supplier):
    
    user = frappe.session.user
    
    user_roles = frappe.get_roles(user)
    
    is_alpla_admin = "Alpla Administrator" in user_roles or "Administrator" in user_roles
        
    return ( supplier.qp_status not in ("En revisión", "Aprobado")) and not is_alpla_admin