from qp_supplier_front.services.get_data import get_supplier
import frappe

def handler(tax_id):
    
    if frappe.db.exists("Supplier", tax_id):
        
        return get_supplier(tax_id)