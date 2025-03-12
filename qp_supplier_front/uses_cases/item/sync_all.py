import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import ITEM_ALL
from datetime import datetime

current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
owner = "Administrator"

@frappe.whitelist()
def handler():
    
    result = send_request(ITEM_ALL)
    
    if "status" not in result or result["status"] != 200:
        
        frappe.throw("Error al comunicarse con el servicio de productos")

    if "items" not in result or not result["items"]:
        
        frappe.throw("Error al consultar la lista de productos")
    
    items_result = result["items"]
    
    create_uoms(items_result)
    
    create_items(items_result)   
        
def create_items(items_result):
    
    items_new = {}
    
    item_codes = frappe.db.get_list('Item', filters={'item_code': ["in", [item_result.get('itemId') for item_result in items_result]]}, pluck='item_code')
    
    for item in items_result:
        
        if item.get("itemId") not in item_codes and item.get("itemId") not in  items_new:
            
            items_new[item.get("itemId")] = item
    
    if items_new:
        
        items = []
        
        for item in items_new.values():
            
            if item.get("itemId") not in item_codes:
                
                item_code = item.get("itemId")
                item_name = item.get("itemDescription")
                item_group = "Todos los grupos de artículos"
                qp_location = item.get("location")
                qp_qty = item.get("quantityAvailable")
                qp_info = item.get("itemInfo")
                qp_data = item.get("itemData")
                qp_type = item.get("itemType")
                qp_class = item.get("class")
                stock_uom = item.get("unitOfMeasurePlan")
                
                #qp_info = item.get("priceLevel") no se que hacer con la lista de precios
                
                items.append((item_code, item_code, item_name, item_group, qp_location,
                            qp_qty, qp_info, qp_data, qp_type, qp_class, stock_uom,
                            current_time, current_time, owner, owner))                  
                                
        if items:
            
            frappe.db.sql("""
                INSERT INTO `tabItem` (name, item_code, item_name, item_group, qp_location, qp_qty, qp_info, qp_data, qp_type, qp_class, stock_uom, creation, modified, owner, modified_by)
                VALUES {values}
            """.format(values=', '.join(str(item) for item in items)))
        frappe.db.commit()
def create_uoms(items_result):
    
    uom_codes = frappe.db.get_list('UOM', filters={'uom_name': ["in", [item_result.get('unitOfMeasurePlan') for item_result in items_result]]}, pluck='uom_name')
    
    uom_codes_upper = [uom.upper() for uom in uom_codes]
    
    uoms_new = set([item.get("unitOfMeasurePlan") for item in items_result if item.get("unitOfMeasurePlan").upper() not in uom_codes_upper])
    
    if uoms_new:
        
        uoms = []
        
        for stock_uom in uoms_new:
            
            uoms.append((stock_uom, stock_uom, current_time, current_time, owner, owner))
        
        if uoms:
        
            frappe.db.sql("""
                INSERT INTO `tabUOM` (name, uom_name, creation, modified, owner, modified_by)
                VALUES {values}
            """.format(values=', '.join(str(uom) for uom in uoms)))