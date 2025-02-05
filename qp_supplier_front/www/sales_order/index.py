import frappe

def get_context(context):
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    context.supplier_id = supplier_id