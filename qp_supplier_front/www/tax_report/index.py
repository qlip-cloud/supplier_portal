import frappe
from qp_supplier_front.services.get_data import has_recent_news

def get_context(context):
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    context.init_fiscal_year  = frappe.db.get_single_value('qp_SP_MasterSetup', 'init_fiscal_year')

    context.has_recent_news = has_recent_news()
    