import frappe
from qp_supplier_front.www.information.index import get_is_alpla_admin

def get_home_page(user):
    
    if user == "Guest":
        return "/login"
    
    user_roles = frappe.get_roles(user)
    
    if get_is_alpla_admin(user_roles):
        return "/app"
    
    config = frappe.get_single("qp_SP_MasterSetup")
    return "/welcome" if config.redirect_to_welcome else "/information"

def on_session_creation_redirect():
    
    user = frappe.session.user
    
    if user == "Guest":
        return

    user_roles = frappe.get_roles(user)

    if get_is_alpla_admin(user_roles):
        return

    config = frappe.get_single("qp_SP_MasterSetup")
    frappe.local.response["home_page"] = "/welcome" if config.redirect_to_welcome else "/information"