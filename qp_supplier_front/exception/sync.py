class ExceptionSyncResponse(Exception):
    
    def __init__(self, endpoint):
        
        super().__init__(f"Error en comunicación con el servicio {endpoint}")

class ExceptionSyncResponseEmpty(Exception):
    
    def __init__(self, request_key):
        
        super().__init__(f"No se pudo conseguir la clave {request_key} en la respuesta del servidor")

class ExceptionSyncNoNewRecords(Exception):
    
    def __init__(self, doctype):
        
        super().__init__(f"No hay nuevos registros para {doctype}")

class ExceptionSyncProductNotFound(Exception):
    
    def __init__(self, request_list_key_id):
        
        super().__init__(f"Producto {request_list_key_id} no esta registrado")
        
class ExceptionSyncRequestNotList(Exception):
    
    def __init__(self, request_key_id):
        
        super().__init__(f"No hay lineas para {request_key_id}")
        
class ExceptionSyncDocNotList(Exception):
    
    def __init__(self, doctype):
        
        super().__init__(f"No hay lineas para {doctype}")
        
class ExceptionAmountMaxLengthNotValid(Exception):
    
    def __init__(self, amount, item_code, order):
        
        super().__init__(f"La longitud del monto del producto {item_code} de la orden {order} no es soportado por el sistema {amount}")