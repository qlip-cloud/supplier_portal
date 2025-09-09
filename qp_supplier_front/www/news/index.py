import frappe
from qp_supplier_front.uses_cases.news.get import get_published_news

def get_context(context):
  context.no_cache = True
  
  query_params = frappe.request.args
  
  supplier_id = query_params.get("supplier")
  
  context.supplier_id = supplier_id
  
  context.news = get_published_news(limit=10)

  return context