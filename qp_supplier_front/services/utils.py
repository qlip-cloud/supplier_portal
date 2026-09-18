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
    

def sanitize_message(message):
    """Normaliza un mensaje para persistirlo sin romper la escritura en BD.

    Las respuestas externas pueden incluir JSON con comillas, saltos de linea
    y caracteres de control que, al insertarse en una alerta/notificacion,
    generan errores de sintaxis SQL (1064). Se compacta el texto, se eliminan
    caracteres de control y se acota la longitud.
    """
    text = "".join(
        ch for ch in str(message or "")
        if ord(ch) >= 32 or ch in "\n\r\t"
    ).replace("\x00", "")
    return " ".join(text.split())[:2000]
    
    