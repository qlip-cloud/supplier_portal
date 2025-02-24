import frappe
import json

def save_to_redis(data_list, key):
    
    cache = frappe.cache()
    
    cache.set(key, json.dumps(data_list))

def get_paginated(page, key):
    
    page_size = 50
    
    cache = frappe.cache()
    
    invoices = json.loads(cache.get(key))
    
    start = (page - 1) * page_size
    
    end = start + page_size
    
    return invoices[start:end]

