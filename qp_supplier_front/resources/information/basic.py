import frappe
from qp_supplier_front.uses_cases.information.basic.update import handler as update_basic
from qp_supplier_front.uses_cases.information.basic.save import handler as save_basic
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def update(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name):
    
    method = frappe.local.request.method
    
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        if method == "POST":
        
            msg += " <br> Sera redireccionado para completar la informacion de proveedor"
            result = save_basic(supplier_name, id_type_name, tax_id, phone_number, business_type_name)
        
        elif method == "PUT":
            
            
            result = update_basic(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear proveedor: {str(error)}"
        
        response(500,  msg)
        