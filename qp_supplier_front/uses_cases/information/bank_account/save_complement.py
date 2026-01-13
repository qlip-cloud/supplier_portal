
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import handler as validate_field

def handler(supplier_id, qp_public_resource_management, qp_public_activity, qp_public_recognition, qp_link_politically_exposed, qp_detail_politically_exposed):
    
    valid_code = "bank_account_complement"
    
    supplier = get_supplier(supplier_id)
    
    update_complement_bank_account(supplier, qp_public_resource_management, qp_public_activity, qp_public_recognition, qp_link_politically_exposed, qp_detail_politically_exposed)
    
    dual_field = [("qp_link_politically_exposed","qp_detail_politically_exposed")]
    dual_field = [
        {
            "condition_value": qp_link_politically_exposed,
            "condition_name": "qp_link_politically_exposed",
            "dependent_value": qp_detail_politically_exposed,
            "dependent_name": "qp_detail_politically_exposed",
        }
    ]

    validate_field(
        supplier,
        valid_code,
        0,
        dual_field,
        qp_public_resource_management=qp_public_resource_management,
        qp_public_activity=qp_public_activity,
        qp_public_recognition=qp_public_recognition,
    )

    
    return {
        "supplier": supplier.as_dict()
    }
    
def update_complement_bank_account(supplier, qp_public_resource_management, qp_public_activity, qp_public_recognition, qp_link_politically_exposed, qp_detail_politically_exposed):
    
    supplier.qp_public_resource_management = qp_public_resource_management
    supplier.qp_public_activity = qp_public_activity
    supplier.qp_public_recognition = qp_public_recognition
    supplier.qp_link_politically_exposed = qp_link_politically_exposed
    supplier.qp_detail_politically_exposed = qp_detail_politically_exposed