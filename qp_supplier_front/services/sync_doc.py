import json
import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.exception.sync import ExceptionSyncResponseEmpty, ExceptionSyncNoNewRecords, ExceptionSyncProductNotFound, ExceptionSyncRequestNotList, ExceptionSyncDocNotList, ExceptionSyncResponse

def setup_doc(supplier_id, endpoint, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list, doctype_list_key_id, is_validate_items, get_doc_base ,set_item):
    
    message = None
    title = f"Error sync {doctype}"
    items_code = None
    result = None
    try:
        
        result = get_result(endpoint, supplier_id)
        
        if is_validate_items:
            
            items_code = frappe.get_list(doctype_list, pluck = doctype_list_key_id)
        
        docs_new = get_docs_new(result, request_key, request_key_id, doctype_key, doctype)
        
        set_doc(result, docs_new, request_key, request_key_id, request_list_key, doctype, items_code, doctype_list_key, request_list_key_id, is_validate_items, get_doc_base, set_item)
    
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
        
def set_doc(result, docs_new, request_key, request_key_id ,request_list_key, doctype, items_code, doctype_list_key, request_list_key_id, is_validate_items, get_doc_base, set_item):    
    
    assertRequestValid(result, request_key)
    
    assertDocNewNotEmpty(docs_new, doctype)
                        
    for doc_new in docs_new:
        
        key_id = doc_new.get(request_key_id)
        
        title=f"Error sync {doctype}: {key_id}"
        
        try:
            
            doc = get_doc_base(doctype, doc_new, request_key_id)
            
            set_doc_list(doc, doc_new, doctype, request_list_key, items_code, request_list_key_id, doctype_list_key, request_key_id, is_validate_items, set_item)
            
            set_doc_control(doc, doc_new, request_list_key, doctype_list_key)
            
            doc.insert(ignore_permissions=True, ignore_links=True, ignore_if_duplicate=True, ignore_mandatory=True)
            
            sync_item(doc, doc_new, items_code, set_item, doctype, doctype_list_key, request_list_key_id, request_list_key)
            
        except (ExceptionSyncDocNotList, ExceptionSyncRequestNotList) as e:
            
            doc.qp_is_error = True
            
            title = str(e)
            
            doc.append("lines_errors", {
                "line":0,
                "code": 0,
                "error": title
            })
            
            pass
        
        except (Exception) as e:
            
            title = str(e)
            
            doc.qp_is_error = True
            
            doc.append("lines_errors", {
                "line":0,
                "code": 0,
                "error": title
            })
            
            pass
        
        finally:
            
            if doc.qp_is_error == True:
                            
                frappe.log_error(message=json.dumps(doc_new), title=title) 
            
            frappe.db.commit()             
        
def sync_item(doc, doc_new, items_code, set_item, doctype, doctype_list_key, request_list_key_id, request_list_key):
    
    if not doc.qp_is_item_sync:
        
        frappe.enqueue(f"qp_supplier_front.services.background.set_item.handler", doc = doc, products=doc_new.get(request_list_key)[30:], items_valid = items_code, key_item =  doctype_list_key, key_id = request_list_key_id, set_item = set_item, queue='long', is_async=True, timeout=14400, job_name=f"send sync {doctype} doc {doc.name}")
                
def set_doc_control(doc, doc_new, request_list_key, doctype_list_key):
    
    assertDocListNotEmpty(doc, doctype_list_key)
    
    doc.qp_item_sync = len(doc_new.get(request_list_key))
        
    doc.qp_item_count = len(doc.get(doctype_list_key))
    
    doc.qp_is_item_sync = doc.qp_item_sync == doc.qp_item_count       
                       
def set_doc_list(doc, doc_new, doctype, request_list_key, items_code, request_list_key_id, doctype_list_key, request_key_id, is_validate_items, set_item):
    
    count = 0
    
    assertRequestListNotEmpty(doc_new.get(request_list_key), request_key_id)
    
    message=json.dumps(doc_new)
    
    for item in doc_new.get(request_list_key)[:30]:
        
        title=f"Error sync {doctype}: {item.get(request_key_id)}"

        try:
            
            count += 1
             
            assertProductExist(item.get(request_list_key_id), items_code, is_validate_items)
            
            doc.append(doctype_list_key, set_item(item))
        
        except ExceptionSyncProductNotFound as e:  
            title = str(e)
            
            doc.qp_is_error = True
            
            doc.append("lines_errors", {
                "line":count,
                "code": item.get(request_list_key_id),
                "error": title
            })
            message=json.dumps(item)
            pass
        
        except Exception as e:
            
            doc.qp_is_error = True
            
            title = str(e)
            
            doc.append("lines_errors", {
                "line":0,
                "code": 0,
                "error": title
            })
            message=json.dumps(item)
            pass
            
        finally:            
            
            if doc.qp_is_error == True:
            
                frappe.log_error(message=message, title=title)

def get_docs_new(result, request_key, request_key_id, doctype_key, doctype):
    
    requests_id = [request.get(request_key_id) for request in result[request_key]]
    
    doctypes_id = frappe.get_list(doctype, filters = {doctype_key: ["in", requests_id]}, pluck = doctype_key)
            
    docs_new = []
    
    count = 0

    for request_id in result[request_key]:
        
        if request_id.get(request_key_id) not in doctypes_id:
            
            docs_new.append(request_id)
            
            count += 1
            
            if count == 45:
                
                break
            
    return docs_new

def get_result(endpoint, supplier_id):
    
    result = send_request(endpoint, param=supplier_id)
    
    assertResponse(result, endpoint)
        
    return result

def assertResponse(result, endpoint):
    
    if "status" not in result or result["status"] != 200:
        
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