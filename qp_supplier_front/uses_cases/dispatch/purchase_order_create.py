import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request_status
from qp_supplier_front.constant.endpoint import DISPATCH_PURCHASE_ORDER_CREATE

def handler(supplier_id, dispatchs_id):
    
    assert_user_is_supplier()
    
    supplier = frappe.get_doc("Supplier", supplier_id)
    
    assert_that_user_has_dispatch_setup(supplier)
    
    assert_that_supplier_has_item_number(supplier)
    
    assert_that_dispatch_is_not_completed(dispatchs_id)

    dispatchs = get_dispatchs(supplier_id, dispatchs_id)
    
    parchase_order = create_purchase_order(dispatchs, supplier.qp_item_number, supplier.name)
    
    send_purchase_order(parchase_order)
    
    update_dispaths(dispatchs_id)

    frappe.db.commit()
    
def assert_user_is_supplier():
    pass

def assert_that_user_has_dispatch_setup(supplier):
    
    pass

def assert_that_supplier_has_item_number(supplier):
    pass 

def assert_that_dispatch_is_not_completed(dispatchs_id):
    pass


def get_dispatchs(supplier_id, dispatchs_id):
    
    return frappe.get_list("qp_SP_Dispatch", filters = {"name": ["IN" , dispatchs_id], "supplier": supplier_id}, fields = ["*"])
    
def create_purchase_order(dispatchs, item_number, vendor_id):
    
    purchase_order = frappe.new_doc("qp_SP_DispatchPurchaseOrder")
    
    purchase_order.init(vendor_id = vendor_id)
    
    purchase_order.set_bol_details(dispatchs, item_number)
    
    purchase_order.insert()
    
    purchase_order.set_subtotal()
    
    purchase_order.set_payload()
    
    return purchase_order
    
def send_purchase_order(purchase_order):
    
    result, status = send_request_status(endpoint_code = DISPATCH_PURCHASE_ORDER_CREATE, payload=purchase_order.get_payload())
        
    assert_that_result_valid(result, status, purchase_order)
    
    purchase_order.save_is_sync(json.dumps(result))
    
def update_dispaths(dispatchs):
    
    user_id = frappe.session.user
    
    placeholders = ", ".join(["%s"] * len(dispatchs_str))
    
    dispatchs_str = str(tuple(dispatchs))
    
    sql = """
            UPDATE `tabqp_SP_Dispatch`
            SET 
                is_sync = 1,
                modified = NOW(),
                modified_by = %s
            WHERE name IN ({0})
        """.format(placeholders)
          
    values = [user_id] + dispatchs

    frappe.db.sql(sql, values)
    
def assert_that_result_valid(result, status, purchase_order):
    
    if status != 200:
        
        error_interno = ""
        
        message = ""
        
        if "errorInterno" in result:
            
            error_interno = result.get("errorInterno")
            
            message = result.get("Message")
        
        
        if "Description" in result:
            
            error_interno = result.get("Description")
            
            message = result.get("Description")
            
        purchase_order.save_is_error(error_interno)
                
        frappe.db.commit()
				
        frappe.throw(message)