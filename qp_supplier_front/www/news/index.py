import frappe
from qp_supplier_front.uses_cases.news.get import get_published_news
from qp_supplier_front.services.get_data import has_recent_news

def get_context(context):
  context.no_cache = True
  
  query_params = frappe.request.args
  
  supplier_id = query_params.get("supplier")
  
  context.supplier_id = supplier_id
  
  context.news = get_published_news()

  context.has_recent_news = has_recent_news()

  user = frappe.session.user
        
  user_roles = frappe.get_roles(user)

  context.is_alpla_admin = "Alpla Administrator" in user_roles or "Administrator" in user_roles

  return context