import frappe
from qp_supplier_front.www.information.index import get_is_alpla_admin

def get_home_page(user):    
    
    if user == "Guest":
        
        return "/login"
    
    user_roles = frappe.get_roles(user)
    
    if get_is_alpla_admin(user_roles):
    
        return "/app"
    
    return "/welcome"
    