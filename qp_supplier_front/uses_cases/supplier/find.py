from qp_supplier_front.services.get_data import get_supplier, get_supplier_phone
import frappe

def handler(tax_id):
    
    if frappe.db.exists("Supplier", tax_id):
        
        supplier = get_supplier(tax_id)
        
        return {
            "name": supplier.name,
            "supplier_name": supplier.supplier_name,
            "qp_asigned": supplier.qp_asigned,
            "phone_number": get_supplier_phone(supplier)
        }