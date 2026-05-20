from qp_supplier_front.services.get_data import get_supplier
APPROVE = "Aprobado"
from qp_supplier_front.constant.endpoint import SUPPLIER_INSERT, SUPPLIER_UPDATE, SUPPLIER_FIND
from qp_supplier_front.services.get_data import get_party, get_dynamic_link, get_bank_accounts
from qp_supplier_front.services.utils import add_log
from qp_supplier_front.www.information.index import get_is_alpla_admin
from qp_authorization.use_case.bearer.authorize import send_request
import frappe
import json
def handler(supplier_id):
    
    user = frappe.session.user

    user_roles = frappe.get_roles(user)
    
    assert_that_user_has_permission(user_roles)
    
    supplier = get_supplier(supplier_id)
    
    supplier.qp_preapproved = True

    supplier.save()

    return {
        "supplier": supplier,
        "is_alpla_admin": get_is_alpla_admin(user_roles,only_admin = True)
    }

def assert_that_user_has_permission(user_roles):
     
    if not get_is_alpla_admin(user_roles, "Alpla Compras"):
        
        frappe.throw("No tiene permiso para realizar esta funcion")    