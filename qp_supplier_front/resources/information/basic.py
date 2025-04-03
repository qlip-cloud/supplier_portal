import frappe
from qp_supplier_front.uses_cases.information.basic.update import handler as update_basic
from qp_supplier_front.uses_cases.information.basic.save import handler as save_basic
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def update(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name, qp_is_foreigner_supplier):
    
    method = frappe.local.request.method
    
    try:
        
        msg = "Los datos han sido creados correctamente"
        msg_redirect = " <br> Sera redireccionado para completar la informacion de proveedor"
        is_exist = frappe.db.exists("Supplier", {"tax_id": tax_id, "qp_asigned": False})
        
        if method == "PUT" or is_exist:
            
            if (is_exist):
            
                msg += msg_redirect
                
                supplier_id = tax_id
                
            result = update_basic(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name, qp_is_foreigner_supplier)
            
            
                
        elif method == "POST":
            
            msg += msg_redirect
            
            result = save_basic(supplier_name, id_type_name, tax_id, phone_number, business_type_name, qp_is_foreigner_supplier)
        
        response(200,  msg, result)
        
    except Exception as error:
        
        msg = f"Error al crear proveedor: {str(error)}"
        
        response(500,  msg)
        