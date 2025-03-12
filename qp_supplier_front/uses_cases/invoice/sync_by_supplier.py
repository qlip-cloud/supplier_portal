import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import INVOICE_SUPPLIER_ID

def handler(supplier_id):
    
    result = send_request(INVOICE_SUPPLIER_ID, param=supplier_id)
    
    if "status" not in result or result["status"] != 200:
        
        frappe.throw("Error al comunicarse con el servicio de productos")

    if "invoices" in result and result["invoices"]:
        
        invoices_id = [invoice.get("invoiceId") for invoice in result["invoices"]]
        
        purchases_id = frappe.get_list("Purchase Invoice", filters = {"qp_invoice_id": ["in", invoices_id]}, pluck = "qp_invoice_id")
        
        invoices_new = [invoice for invoice in result["invoices"] if invoice.get("invoiceId") not in purchases_id]
        
        if invoices_new:
            
            for invoice in invoices_new:
                
                try:
                    doc = frappe.new_doc("Purchase Invoice")
                    
                    doc.qp_invoice_id = invoice.get("invoiceId")
                    doc.qp_create_date = invoice.get("createdate")
                    #doc.posting_date = invoice.get("createdate")
                    doc.qp_due_date = invoice.get("dueDate")
                    #doc.due_date = invoice.get("dueDate")
                    doc.qp_subtotal = invoice.get("subTotal")
                    #doc.net_total = invoice.get("subTotal")
                    doc.qp_tax = invoice.get("tax")
                    doc.qp_total = invoice.get("total")
                    doc.qp_currency = invoice.get("currency")
                    #doc.currency = invoice.get("currency")
                    doc.supplier = invoice.get("vendor")
                    doc.qp_status = invoice.get("status")
                    doc.naming_series = "ACC-PINV-.YYYY.-"
                    
                    for item in invoice.get("products"):
                        
                        doc.append("items", {
                            "item_code": item.get("itemnmbr"),
                            "qp_tax": item.get("taxItem"),
                            "qp_qty": item.get("quantity"),
                            "qty": 1,
                            "qp_unit_cost": item.get("unitCost"),
                            "rate": 1,
                            "qp_extd_cost": item.get("extdCost"),
                            "conversion_factor": 1
                        })
                    
                    doc.insert(ignore_permissions=True, # ignore write permissions during insert
                                ignore_links=True, # ignore Link validation in the document
                                ignore_if_duplicate=True, # dont insert if DuplicateEntryError is thrown
                                ignore_mandatory=True)
                    
                except Exception as e:
                    pass
                
            frappe.db.commit()