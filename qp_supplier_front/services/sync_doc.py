import json
import frappe
from datetime import datetime 
from qp_supplier_front.exception.sync import ExceptionSyncResponseEmpty, ExceptionSyncNoNewRecords, ExceptionSyncProductNotFound, ExceptionSyncRequestNotList, ExceptionSyncDocNotList, ExceptionSyncResponse
from qp_supplier_front.services.background.set_item import handler as set_sync_item
from qp_supplier_front.util.command import create_doc
from qp_authorization.use_case.bearer.authorize import send_request

NOW = str(datetime.now())

def setup_doc(result, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list, doctype_list_key_id, is_validate_items, get_doc_base, insert_doc, set_item_default = None):
    
        
    message = None
    title = f"Error sync {doctype}"
    items_code = {}
    
    try:
        
        if is_validate_items:
                        
            items = frappe.get_list(doctype_list, fields = ["*"])
            
            for item in items:
                
                items_code.update({item[doctype_list_key_id]: item})
        
        docs_new = get_docs_new(result, request_key, request_key_id, doctype_key, doctype)
        
        set_doc(result, docs_new, request_key, request_key_id, request_list_key, doctype, items_code, doctype_list_key, request_list_key_id, is_validate_items, get_doc_base, insert_doc, set_item_default)
              
        frappe.db.commit()
        
    except ExceptionSyncResponse as e:
        
        title = str(e)
        
        message = json.dumps(result)
    
    except ExceptionSyncResponseEmpty as e:
        
        title = str(e)
        
        message = json.dumps(docs_new[-1])
    
    except ExceptionSyncNoNewRecords as e:
        
        pass
        
    except Exception as e:

        message = str(e)
        
    finally:
        
        if message:
                    
            frappe.log_error(message=message, title=title)
            frappe.throw(title)  
                   
def get_last_creation(doctype, supplier_id, order_by):
    
    latest_record = frappe.db.get_list(doctype, filters = {"supplier": supplier_id}, pluck = order_by, order_by=f"{order_by} desc", limit=1)  
            
    return latest_record[0] if latest_record else None

def set_doc(result, docs_new, request_key, request_key_id ,request_list_key, doctype, items_code, doctype_list_key, request_list_key_id, is_validate_items, get_doc_base, insert_doc, set_item_default = None):    
    
    assertRequestValid(result, request_key)
    
    assertDocNewNotEmpty(docs_new, doctype)
    
    docs = {}    
    items ={}
    errors ={}
    
    for doc_new in docs_new:
        
        doc_id = None
        
        qp_is_error = False
                   
        title=f"Error sync {doctype}:" + doc_new.get(request_key_id)
                
        doc_id  = doc_new.get(request_key_id) + ":" + doc_new.get("vendor")

        try:
            
            get_doc_base(doc_new, request_key_id, docs, doc_id)
            
            set_doc_list(doc_new, doctype, request_list_key, items_code, request_list_key_id, doctype_list_key, request_key_id, is_validate_items, items, errors, doc_id, set_item_default)
            
            
        except (ExceptionSyncDocNotList, ExceptionSyncRequestNotList) as e:
            
            #doc.qp_is_error = True
            
            title = str(e)
            
            qp_is_error = True
            
            
            pass
        
        except (Exception) as e:
            
            title = str(e)
            
            qp_is_error = True

            pass
        
        finally:
            
            if qp_is_error == True:                
                
                frappe.log_error(message=json.dumps(doc_new), title=title) 
    
    insert_doc(docs, items)
    
    insert_erros(errors)
    
def sync_item(doc, doc_new, items_code, set_item, doctype, doctype_list_key, request_list_key_id, request_list_key):
    
    if set_item and not doc.qp_is_item_sync:

        set_sync_item(doc = doc, products=doc_new.get(request_list_key), items_valid = items_code, key_item =  doctype_list_key, key_id = request_list_key_id, set_item = set_item)

                
def set_doc_control(doc, doc_new, request_list_key, doctype_list_key):
    
    if request_list_key and doctype_list_key:
        
        assertDocListNotEmpty(doc, doctype_list_key)
        
        doc.qp_item_sync = len(doc_new.get(request_list_key))
            
        doc.qp_item_count = len(doc.get(doctype_list_key))
        
        doc.qp_is_item_sync = doc.qp_item_sync == doc.qp_item_count       
                       
def set_doc_list(doc_new, doctype, request_list_key, items_code, request_list_key_id, doctype_list_key, request_key_id, is_validate_items, items, errors, doc_id, set_item_default = None):
    
    if set_item_default:
        
        count = 0
        
        qp_is_error = False
        
        assertRequestListNotEmpty(doc_new.get(request_list_key), request_key_id)
        
        message=json.dumps(doc_new)
        
        for key, item in enumerate(doc_new.get(request_list_key)):
            
            title=f"Error sync {doctype}: {item.get(request_list_key_id)}"
            
    
            try:
                
                count += 1
                
                assertProductExist(item.get(request_list_key_id), items_code, is_validate_items)
                
                set_item_default(item, items, doc_id, items_code)
                
                #doc.append(doctype_list_key, set_item_default(item))
            
            except ExceptionSyncProductNotFound as e:
                
                title = str(e)

                qp_is_error = True
                
                error = {
                    "line":count,
                    "code": item.get(request_list_key_id),
                    "error": title
                }  

                message=json.dumps(item)
                
                set_error(error, errors, doc_id, item.get(request_list_key_id), doctype, key)
                
                pass
            
            except Exception as e:
                
                title = str(e)
                
                qp_is_error = True
                
                error = {
                    "line":0,
                    "code": 0,
                    "error": title
                }  
                
                set_error(error, errors, doc_id, item.get(request_list_key_id), doctype, key)
                
                message=json.dumps(item)
                
                pass
                
            finally:            
                
                if qp_is_error == True:
                
                    frappe.log_error(message=message, title=title)

def get_docs_new(result, request_key, request_key_id, doctype_key, doctype):
    
    requests_id = [request.get(request_key_id) for request in result[request_key]]
    
    doctypes_id = frappe.get_list(doctype, filters = {doctype_key: ["in", requests_id]}, pluck = doctype_key)
            
    docs_new = []
    
    for request_id in result[request_key]:
        
        if request_id.get(request_key_id) not in doctypes_id:
            
            docs_new.append(request_id)
            
    return docs_new

def get_result(endpoint, supplier_id, latest_record = None):
    
    param = f"{supplier_id}"
    
    url = endpoint["all"]
    
    if latest_record:
        
        param += f"/{latest_record}/{datetime.today()}"
        
        url = endpoint["range"]
        
    result = send_request(url, param=param)
        
    return result


def set_error(error, errors, doc_id, item_code, doctype, key):
    error_id = f"{doc_id}:{item_code}:{key}"
    errors.update({error_id:(
            error_id,
            error.get("line"),
            error.get("code"),
            error.get("error"),
            doc_id,
            "lines_errors",
            doctype,
            NOW,
            NOW,
            "Administrator",
            "Administrator"
        )})
    
def insert_erros(docs):
    
    if docs:
        
        table = "`tabqp_SP_LineErrorSync`"
    
        doc_fiels = "(name, line, code, error, parent, parentfield, parenttype, creation, modified, modified_by, owner)"
    
        create_doc(docs, doc_fiels, table)

def assertResponse(result, endpoint):
    
    if "status" not in result or result["status"] != 200:
        
        frappe.log_error(message=json.dumps(result), title="assertResponse")
        
        raise ExceptionSyncResponse(endpoint)
                
def assertRequestValid(result, request_key):
    
    if request_key not in result or not result[request_key]:
        
        raise ExceptionSyncResponseEmpty(request_key)

def assertDocNewNotEmpty(docs_new, doctype):
    
    if not docs_new:
        
        raise ExceptionSyncNoNewRecords(doctype)

def assertRequestListNotEmpty(resquest_list, request_key_id):
    
    if not resquest_list:
        
        raise ExceptionSyncRequestNotList(request_key_id)

def assertProductExist(request_list_key_id, items_code, is_validate_items):
    
    if is_validate_items and request_list_key_id not in items_code:
        
        raise ExceptionSyncProductNotFound(request_list_key_id)
    
def assertDocListNotEmpty(doc, doctype_list_key):
    
    if not hasattr(doc, doctype_list_key) or not doc.get(doctype_list_key):
        
        raise ExceptionSyncDocNotList(doc.doctype)