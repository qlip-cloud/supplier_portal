import frappe

def get_context(context):
    context.no_cache = True
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    context.supplier_id = supplier_id
    
    context.init_fiscal_year  = frappe.db.get_single_value('qp_SP_MasterSetup', 'init_fiscal_year')
    