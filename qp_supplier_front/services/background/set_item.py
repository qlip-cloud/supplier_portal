import frappe

def handler(doc, products, items_valid, key_item, key_id, set_item):
    
    if not doc.qp_is_item_sync and not doc.qp_process_item_sync:
        
        doc.qp_process_item_sync  = True

        try:
            
            if products:
    
                try:
                
                    for key, item in enumerate(products):
                                                                                    
                        try:
                            
                            if items_valid:
                                
                                validate_item(item, items_valid, key_id)
                            
                            doc.append(key_item, set_item(item))
                            
                        except Exception as e:
                            doc.append("lines_errors", {
                                "line":key,
                                "code": "Lote",
                                "error": str(e)
                            })
                            
                    doc.qp_item_count = len(doc.items)
                    
                    doc.qp_is_item_sync = doc.qp_item_sync == doc.qp_item_count
                    
                except Exception as e:
                    doc.append("lines_errors", {
                        "line": key,
                        "code": item.get("itemnmbr"),
                        "error": str(e)
                    })                           
                    
                finally:
                
                    doc.save()
                        
                    frappe.db.commit()                        
                            
                        
        except Exception as e:
            
            doc.append("lines_errors", {
                "line":0,
                "code": "General",
                "error": str(e)
            })
        
        finally:
            
            doc.qp_process_item_sync  = False
            
            doc.save()
                            
            frappe.db.commit()
        
        
def validate_item(item, items_valid, key):
    
    if not item[key] in items_valid:

        raise Exception("El producto no esta registrado en el sistema")
    
            

            