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
        
        orders_new = [order for order in result["orders"] if order.get("orderId") not in sales_orders_id]
        
        if orders_new:
            
            for order in orders_new:
                try:
                    doc = frappe.new_doc("Purchase Order")
                    
                    doc.qp_order_id = order.get("orderId")
                    doc.qp_create_date = order.get("docDate")
                    doc.supplier = order.get("vendor")
                    doc.qp_due_date = order.get("prmDate")
                    doc.posting_date = order.get("docDate")
                    doc.schedule_date = datetime.now()
                    
                    #doc.due_date = order.get("dueDate")
                    
                    #doc.qp_status = order.get("status")
                    
                    for item in order.get("products"):
                        
                        doc.append("items", {
                            "item_code": item.get("itemnmbr"),
                            "qp_qty": item.get("qtyOrder"),
                            "qty": 1,
                            "qp_unit_cost": item.get("unitCost"),
                            "rate": item.get("unitCost"),
                            "qp_extd_cost": item.get("extdCost"),
                            #"conversion_factor": 1
                        })
                    
                    doc.insert(ignore_permissions=True, # ignore write permissions during insert
                                ignore_links=True, # ignore Link validation in the document
                                ignore_if_duplicate=True, # dont insert if DuplicateEntryError is thrown
                                ignore_mandatory=True)
                    
                except Exception as e:
                    
                    pass
            frappe.db.commit()