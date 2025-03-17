import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import PAYMENT_SUPPLIER_ID
from datetime import datetime
def handler(supplier_id):
    
    result = send_request(PAYMENT_SUPPLIER_ID, param=supplier_id)
    
    if "status" not in result or result["status"] != 200:
        
        frappe.throw("Error al comunicarse con el servicio de productos")

    if "payments" in result and result["payments"]:
        
        receipts_id = [receipt.get("vchrnmbr") for receipt in result["payments"]]
        
        sales_receipts_id = frappe.get_list("Purchase Receipt", filters = {"qp_receipt_id": ["in", receipts_id]}, pluck = "qp_receipt_id")
        
        receipts_new = []
        
        count = 0

        for receipt in result["payments"]:
            
            if receipt.get("vchrnmbr") not in sales_receipts_id:
                
                receipts_new.append(receipt)
                
                count += 1
                
                if count == 45:
                    break
                
        if receipts_new:
            
            for receipt in receipts_new:
                try:
                    if (receipt.get("reference")):
                        
                        doc = frappe.new_doc("Purchase Receipt")
                        doc.qp_receipt_id = receipt.get("vchrnmbr")
                        doc.qp_create_date = receipt.get("dinvodof")
                        doc.supplier = receipt.get("vendor")
                        doc.posting_date = receipt.get("docDate")
                        doc.qp_amount = receipt.get("docamnt")
                        doc.base_grand_total = 0
                        doc.grand_total = 0
                        doc.base_rounded_total = 0
                        doc.rounded_total = 0

                        
                        #doc.due_date = receipt.get("dueDate")
                        
                        #doc.qp_status = receipt.get("status")
                        for item in receipt.get("reference")[:30]:
                            
                            doc.append("qp_references", set_item(item))
                            
                        doc.qp_item_sync = len(receipt.get("reference"))
                        
                        doc.qp_item_count = len(doc.qp_references)
                        
                        doc.qp_is_item_sync = doc.qp_item_sync == doc.qp_item_count
                        
                        doc.insert(ignore_permissions=True, # ignore write permissions during insert
                                ignore_links=True, # ignore Link validation in the document
                                ignore_if_duplicate=True, # dont insert if DuplicateEntryError is thrown
                                ignore_mandatory=True)
                        
                        if not doc.qp_is_item_sync:
                        
                            frappe.enqueue(f"qp_supplier_front.services.background.set_item.handler", doc = doc, products=receipt.get("products")[30:], items_valid = None, key_item =  "qp_references", key_id = "aptvchnm", set_item = set_item, queue='long', is_async=True, timeout=14400, job_name=f"send sync receipt doc {doc.name}")
                
                except Exception as e:
                    pass
            
            frappe.db.commit()

def set_item(item):
    return {
        "qp_aptovcnm": item.get("aptvchnm"),
        "qp_seq": item.get("seq"),
        "qp_appldamt": item.get("appldamt"),
        "qp_aptodcnm": item.get("aptodcnm")
        
    }