import frappe
import json

def add_log(title, payload = None, response = None, supplier_id = None, raw_response = None):
    
    request_log = frappe.new_doc("qp_SP_RequestLog")
    
    request_log.title = title
    request_log.response = json.dumps(response)
    request_log.payload = json.dumps(payload)
    request_log.supplier_id = supplier_id

    if raw_response is not None:
        request_log.raw_response = raw_response

    request_log.insert()
    
    