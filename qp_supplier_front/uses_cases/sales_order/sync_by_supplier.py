import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import ORDER_SUPPLIER_ID
from datetime import datetime
def handler(supplier_id):
    
    result = send_request(ORDER_SUPPLIER_ID, param=supplier_id)
    
    if "status" not in result or result["status"] != 200:
        
        frappe.throw("Error al comunicarse con el servicio de productos")

    if "orders" in result and result["orders"]:
        
        orders_id = [order.get("orderId") for order in result["orders"]]
        
        sales_orders_id = frappe.get_list("Purchase Order", filters = {"qp_order_id": ["in", orders_id]}, pluck = "qp_order_id")
        
        items_code = frappe.get_list("Item", pluck = "item_code")
        
        orders_new = []
        
        count = 0

        for order in result["orders"]:
            
            if order.get("orderId") not in sales_orders_id:
                
                orders_new.append(order)
                
                count += 1
                
                if count == 45:
                    break
                
        if orders_new:
                        
            for order in orders_new:
                
                    doc = frappe.new_doc("Purchase Order")
                    
                    doc.qp_order_id = order.get("orderId")
                    doc.qp_create_date = order.get("docDate")
                    doc.supplier = order.get("vendor")
                    doc.qp_due_date = order.get("prmDate")
                    doc.posting_date = order.get("docDate")
                    doc.schedule_date = datetime.now()
                    
                    #doc.due_date = order.get("dueDate")
                    
                    #doc.qp_status = order.get("status")
                                        
                    for item in order.get("products")[:30]:
                        
                        doc.append("items", set_item(item))
                        
                    doc.qp_item_sync = len(order.get("products"))
                    
                    doc.qp_item_count = len(doc.items)
                    
                    doc.qp_is_item_sync = doc.qp_item_sync == doc.qp_item_count
                    
                    doc.insert(ignore_permissions=True, # ignore write permissions during insert
                                ignore_links=True, # ignore Link validation in the document
                                ignore_if_duplicate=True, # dont insert if DuplicateEntryError is thrown
                                ignore_mandatory=True)
                    
                    if not doc.qp_is_item_sync:
                        
                        frappe.enqueue(f"qp_supplier_front.services.background.set_item.handler", doc = doc, products=order.get("products")[30:], items_valid = items_code, key_item =  "items", key_id = "itemnmbr", set_item = set_item, queue='long', is_async=True, timeout=14400, job_name=f"send sync invoice doc {doc.name}")
                        
            frappe.db.commit()
            
def set_item(item):
    return {
        "item_code": item.get("itemnmbr"),
        "qp_qty": item.get("qtyOrder"),
        "qty": 1,
        "qp_unit_cost": item.get("unitCost"),
        "rate": item.get("unitCost"),
        "qp_extd_cost": item.get("extdCost"),
        #"conversion_factor": 1
    }