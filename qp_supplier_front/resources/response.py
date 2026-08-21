import frappe
import traceback

def handler(status ,msg, data = None):
    
    frappe.response['message'] = {
            "status": status,
            "data" : data,
            "msg": msg        
        }
        
    frappe.response['http_status_code'] = status
    
    if status != 200:
        
        frappe.db.rollback()

        traceback.print_exc()

        title = data or msg

        if title and len(str(title)) > 140:
            title = str(title)[:140]

        frappe.log_error(message=frappe.get_traceback(), title = title)       