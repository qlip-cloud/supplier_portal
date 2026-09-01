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

        # frappe.log_error exige un titulo string: un dict (p. ej. data con
        # clasificacion de estado) rompe el insert a tabError Log.
        if not isinstance(title, str):
            title = str(title)

        if title and len(title) > 140:
            title = title[:140]

        frappe.log_error(message=frappe.get_traceback(), title = title)       