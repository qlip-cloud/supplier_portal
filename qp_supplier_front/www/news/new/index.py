import frappe
from qp_supplier_front.uses_cases.news.get import get_article
from qp_supplier_front.www.information.index import get_is_alpla_admin

def get_context(context):
  context.no_cache = True
  
  query_params = frappe.request.args
  

  supplier_id = query_params.get("supplier")
  
  context.supplier_id = supplier_id
  
  user = frappe.session.user
        
  user_roles = frappe.get_roles(user)

  is_alpla_admin = get_is_alpla_admin(user_roles)

  context.is_alpla_admin = is_alpla_admin

  if not is_alpla_admin:
    frappe.throw("No tienes permisos para crear noticias", frappe.PermissionError)

  return context