import frappe
from qp_supplier_front.uses_cases.information.basic.update import handler as update_basic
from qp_supplier_front.uses_cases.information.basic.save import handler as save_basic
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def update(supplier_id, supplier_name, id_type_name, tax_id, phone_number, business_type_name, qp_is_foreigner_supplier=None):
    
    if supplier_name and len(str(supplier_name)) > 65:
        frappe.throw("El nombre excede los 65 caracteres.")
        
    method = frappe.local.request.method

    qp_is_foreigner_supplier = True if qp_is_foreigner_supplier == "true" else False
    
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
        
@frappe.whitelist()
def request_edit(supplier_id):
    try:
        supplier = frappe.get_doc("Supplier", supplier_id)
        supplier.qp_request_edit = True
        supplier.save()
        msg = "Se ha enviado la solicitud de edición correctamente"
        response(200, msg)
    except Exception as error:
        msg = f"Error al enviar la solicitud de edición: {str(error)}"
        response(500, msg)

@frappe.whitelist()
def approve_edit(supplier_id):
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    
    from qp_supplier_front.www.information.index import get_is_alpla_admin
    if not get_is_alpla_admin(user_roles):
        response(403, "No tiene permiso para realizar esta acción")
        return

    try:
        supplier = frappe.get_doc("Supplier", supplier_id)
        supplier.qp_status = "En proceso"
        supplier.qp_request_edit = False
        supplier.save()
        msg = "La solicitud de edición ha sido aprobada correctamente"
        response(200, msg)
    except Exception as error:
        msg = f"Error al aprobar la solicitud de edición: {str(error)}"
        response(500, msg)