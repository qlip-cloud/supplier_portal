import frappe
from qp_supplier_front.www.information.index import get_is_alpla_admin

def handler(supplier):
    
    user = frappe.session.user
    
    user_roles = frappe.get_roles(user)
    
    is_alpla_admin = get_is_alpla_admin(user_roles)
        
    return ( supplier.qp_status not in ("En revisión", "Aprobado")) and not is_alpla_admin