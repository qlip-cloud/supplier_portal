import frappe
import json
from qp_authorization.use_case.bearer.authorize import send_request_status
from qp_supplier_front.constant.endpoint import DISPATCH_PURCHASE_ORDER_CREATE

def handler(supplier_id, dispatchs_id):
    
    assert_user_is_supplier()
    
    supplier = get_supplier(supplier_id)
       
    dispatchs = get_dispatchs(supplier_id, dispatchs_id)
    
    item = get_item(supplier.qp_item_number)
        
    parchase_order = create_purchase_order(dispatchs, item, supplier.name)
    
    send_purchase_order(parchase_order)
    
    update_dispaths(dispatchs_id)

    frappe.db.commit()

def get_supplier(supplier_id):
    
    supplier = frappe.get_doc("Supplier", supplier_id)
    
    assert_that_user_has_dispatch_setup(supplier.qp_is_transporter)
    
    return supplier
    
def get_item(qp_item_number):
    
    assert_that_supplier_has_item_number(qp_item_number)
    
    item = frappe.get_doc("Item", qp_item_number)
    
    return item

def assert_user_is_supplier():
    pass

def assert_that_user_has_dispatch_setup(qp_is_transporter):
    
    if not qp_is_transporter:
        
        frappe.throw("El proveedor no tiene habilitado el servicio de despacho")

def assert_that_supplier_has_item_number(qp_item_number):
    
    if not qp_item_number:
        
        frappe.throw("El proveedor no tiene configurado el producto por defecto para enviar en despacho") 

def assert_that_dispatch_is_not_completed(dispatchs):
    
    dispatchs_completed = list(filter(lambda dispatch: dispatch.get("is_complete"), dispatchs))
    
    if dispatchs_completed:
        
        dispatchs_names = list(map(lambda dispatch: f"<li>{dispatch.bol}</li>", dispatchs_completed))
        
        frappe.throw("Los siguientes despachos ya han sido creados: <br><ul>{}</ul>".format("".join(dispatchs_names)))
    
def get_dispatchs(supplier_id, dispatchs_id):
    
    dispatchs = frappe.get_list("qp_SP_Dispatch", filters = {"name": ["IN" , dispatchs_id], "supplier": supplier_id}, fields = ["*"])
    
    assert_that_dispatch_is_not_completed(dispatchs)
    
    return dispatchs
    
def create_purchase_order(dispatchs, item, vendor_id):
    
    purchase_order = frappe.new_doc("qp_SP_DispatchPurchaseOrder")
    
    purchase_order.setup(vendor_id, dispatchs, item.name, item.stock_uom)
    
    purchase_order.insert()
    
    return purchase_order
    
def send_purchase_order(purchase_order):
    
    result, status = send_request_status(endpoint_code = DISPATCH_PURCHASE_ORDER_CREATE, payload=purchase_order.get_payload())
            
    assert_that_result_valid(result, status, purchase_order)
    
    purchase_order.save_is_sync(json.dumps(result))
    
def update_dispaths(dispatchs):
    
    user_id = frappe.session.user
    
    placeholders = ", ".join(["%s"] * len(dispatchs))
        
    sql = """
            UPDATE `tabqp_SP_Dispatch`
            SET 
                is_complete = 1,
                modified = NOW(),
                modified_by = %s
            WHERE name IN ({0})
        """.format(placeholders)
          
    values = [user_id] + dispatchs

    frappe.db.sql(sql, values)
    
def assert_that_result_valid(result, status, purchase_order):
    
    if status not in (200, 201):
        
        error_interno = ""
        
        message = ""
        
        if "errorInterno" in result:
            
            error_interno = result.get("errorInterno")
            
            message = result.get("Message")
        
        
        if "Description" in result:
            
            error_interno = result.get("Description")
            
            message = result.get("Description")
            
        if "title" in result:
            
            error_interno = json.dumps(result.get("errors"))
            
            message = result.get("title")
            
        purchase_order.save_is_error(error_interno)
                
        frappe.db.commit()
				
        frappe.throw(message)