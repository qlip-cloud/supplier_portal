import frappe
from qp_supplier_front.uses_cases.information.shareholder.save import handler as save_shareholder
from qp_supplier_front.uses_cases.information.shareholder.update import handler as update_shareholder
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.information.shareholder.get import get_shareholder


@frappe.whitelist()
def update(supplier_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct, doctype_id = None):
    method = frappe.local.request.method
    
    try:
        
        msg = "Los datos han sido actualizados correctamente"
        if method == "POST":
        
            result = save_shareholder(supplier_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct)
            
        elif method == "PUT":
            
            result = update_shareholder(supplier_id, doctype_id, fullname, nationality, have_resident_another_country, have_american_visa, id_type, tax_id, market_share, authorization_data_processing, supplier_code_conduct)
        
        
        list = frappe.render_template("qp_supplier_front/templates/list/information/shareholders.html", {
            "supplier": result.get("supplier")
        })
        
        result.setdefault("render", {"list": list, "container": "shareholder_list"})
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al actualizar Accionistas o Asociados: {str(error)}"
        
        response(500,  msg)
        
    
        
@frappe.whitelist()
def search_shareholder(shareholder_id):
    
    try:
        
        msg = "Los datos han sido buscados correctamente"
        
        result = get_shareholder(shareholder_id)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al buscados shareholder: {str(error)}"
        
        response(500,  msg)  