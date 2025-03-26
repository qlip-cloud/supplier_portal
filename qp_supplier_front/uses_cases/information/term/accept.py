import frappe
from qp_supplier_front.services.get_data import get_supplier
from datetime import datetime
import pytz

def handler(supplier_id, accept_type):
    colombia_tz = pytz.timezone('America/Bogota')
    supplier = get_supplier(supplier_id)
    
    if accept_type == "qp_accept_autorization_processing":
        
        supplier.qp_accept_autorization_processing = True
        supplier.qp_accept_autorization_processing_user = frappe.session.user
        supplier.qp_accept_autorization_processing_date = datetime.now()
        
    if accept_type == "qp_accept_conduct":
        
        supplier.qp_accept_conduct_code = True
        supplier.qp_accept_conduct_code_user = frappe.session.user
        supplier.qp_accept_conduct_code_date = datetime.now()
    
    supplier.save()
    
    return  supplier.as_dict()