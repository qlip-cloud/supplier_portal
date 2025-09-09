import frappe
from qp_supplier_front.uses_cases.news.get import get_article

def get_context(context):
  context.no_cache = True
  
  query_params = frappe.request.args
  
  article_name = query_params.get("article_name")

  supplier_id = query_params.get("supplier")
  
  context.supplier_id = supplier_id

  print(article_name)
  
  context.article = get_article(article_name)

  return context