import frappe
import json
PAGE_LENGTH = 15

def get_detail(parent_doctype, doctype, name, page = 0):
    
    page_length = 10
    
    start = page * page_length
    
    doc = frappe.get_doc(parent_doctype, name)
    
    list_detail = frappe.get_list(doctype, filters = {"parent": name}, fields = ["*"], start=start,
    page_length=page_length)
    
    total_pages = (doc.qp_item_sync + page_length - 1) // page_length   
         
    return {
        "list_detail": list_detail,
        "total_items": doc.qp_item_sync,
        "total_items_sync": doc.qp_item_count,
        "total_pages": total_pages,
        "page": page
    }
    

def get_paginated(page, doctype, supplier_id, filters = {}):
    
    filters.update({"supplier": supplier_id})
    
    start = page * PAGE_LENGTH
    
    return frappe.get_list(doctype, filters = filters, fields = ["*"], start=start, page_length=PAGE_LENGTH)