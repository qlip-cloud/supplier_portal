import frappe
import json
import os

def execute():
    file_path = '/workspace/development/mentum_localhost/apps/qp_supplier_front/qp_supplier_front/uses_cases/supplier/response.json'
    if not os.path.exists(file_path):
        print("File not found")
        return
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    nits = [v.get('nit') for v in data.get('vendors', []) if v.get('mail') and v.get('mail').strip() != '']
    
    missing_contacts = []
    
    for nit in nits:
        supplier = frappe.db.get_value("Supplier", {"tax_id": nit}, "name")
        if not supplier:
            missing_contacts.append(f"{nit} (No registrado en DB)")
            continue
        
        contacts = frappe.db.sql("""
            SELECT c.name FROM `tabContact` c
            JOIN `tabDynamic Link` dl ON dl.parent = c.name
            WHERE dl.link_doctype = 'Supplier' AND dl.link_name = %s
        """, (supplier,))
        
        if not contacts:
            missing_contacts.append(f"{nit} (Proveedor: {supplier})")
            
    print("=== RESULTADOS ===")
    for m in missing_contacts:
        print(f"SIN CONTACTO: {m}")
    print("==================")
