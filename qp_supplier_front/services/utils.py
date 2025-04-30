import frappe
import json
def add_log(title, payload, response, supplier_id):
    
    request_log = frappe.new_doc("qp_SP_RequestLog")
    
    request_log.title = title
    request_log.response = json.dumps(response)
    request_log.payload = json.dumps(payload)
    request_log.supplier_id = supplier_id
    request_log.insert()
    
    