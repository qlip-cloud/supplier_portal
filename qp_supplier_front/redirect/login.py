import frappe
from qp_supplier_front.www.information.index import get_is_alpla_admin
from qp_supplier_front.services.role_resolver import has_any_documenteme_role


def is_desk_user(user_roles):
    """True si el usuario debe aterrizar en el escritorio (/app).

    Aplica a los administradores Alpla y a cualquier rol de documenteme
    (su rol tiene desk_access, por lo que Frappe los crea como System User).
    """
    return get_is_alpla_admin(user_roles) or has_any_documenteme_role(user_roles)


def get_home_page(user):
    
    if user == "Guest":
        return "/login"
    
    user_roles = frappe.get_roles(user)
    
    if is_desk_user(user_roles):
        return "/app"
    
    config = frappe.get_single("qp_SP_MasterSetup")
    return "/welcome" if config.redirect_to_welcome else "/information"

def on_session_creation_redirect():
    
    user = frappe.session.user
    
    if user == "Guest":
        return

    user_roles = frappe.get_roles(user)

    if is_desk_user(user_roles):
        return

    config = frappe.get_single("qp_SP_MasterSetup")
    frappe.local.response["home_page"] = "/welcome" if config.redirect_to_welcome else "/information"