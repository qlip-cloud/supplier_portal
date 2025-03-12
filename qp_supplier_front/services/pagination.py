import frappe
import json
PAGE_LENGTH = 15

def get_detail(doctype, name, page = 0):
    page_length = 10
    start = page * page_length
    
    list_detail = frappe.get_list(doctype, filters = {"parent": name}, fields = ["*"], start=start,
    page_length=page_length)
    
    total_items = frappe.db.count(doctype, filters = {"parent": name})
    
    
    total_pages = (total_items + page_length - 1) // page_length   
         
    return {
        "list_detail": list_detail,
        "total_items": total_items,
        "total_pages": total_pages,
        "page": page,
    }
    

def get_paginated(page, doctype, supplier_id, filters = {}):
    
    filters.update({"supplier": supplier_id})
    
    start = page * PAGE_LENGTH
    return frappe.get_list(doctype, filters = filters, fields = ["*"], start=start, page_length=PAGE_LENGTH)