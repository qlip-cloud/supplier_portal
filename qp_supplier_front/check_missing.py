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
        
    vendors = data.get('vendors', [])
    
    missing_info = []
    
    for v in vendors:
        vendor_id = v.get('vendorId')
        name = v.get('name')
        mail = v.get('mail', '').strip()
        address_list = v.get('address', [])
        eft_list = v.get('eftInformation') or []
        
        if not vendor_id:
            continue
            
        supplier_name = frappe.db.get_value("Supplier", {"tax_id": vendor_id}, "name")
        if not supplier_name:
            continue
            
        # Check Contact
        has_contact_in_db = False
        if mail:
            has_contact_in_db = bool(frappe.db.sql("""
                SELECT c.name FROM `tabContact` c
                JOIN `tabDynamic Link` dl ON dl.parent = c.name
                WHERE dl.link_doctype = 'Supplier' AND dl.link_name = %s
            """, (supplier_name,)))
            
        # Check Address
        has_address_in_db = False
        if address_list:
            has_address_in_db = bool(frappe.db.sql("""
                SELECT a.name FROM `tabAddress` a
                JOIN `tabDynamic Link` dl ON dl.parent = a.name
                WHERE dl.link_doctype = 'Supplier' AND dl.link_name = %s
            """, (supplier_name,)))
            
        # Check Bank Account
        has_bank_in_db = False
        if eft_list:
            has_bank_in_db = frappe.db.exists("Bank Account", {"party_type": "Supplier", "party": supplier_name})
            
        missing = []
        if mail and not has_contact_in_db:
            missing.append("Contacto")
        if address_list and not has_address_in_db:
            missing.append("Dirección")
        if eft_list and not has_bank_in_db:
            missing.append("Cuenta Bancaria")
            
        if missing:
            missing_info.append({
                "nit": vendor_id,
                "name": name,
                "missing": missing
            })
            
    # Group and sample
    missing_contacts = [x for x in missing_info if "Contacto" in x["missing"]]
    missing_addresses = [x for x in missing_info if "Dirección" in x["missing"]]
    missing_banks = [x for x in missing_info if "Cuenta Bancaria" in x["missing"]]
    
    print("=== CONTACTOS FALTANTES ===")
    for item in missing_contacts[:5]:
        print(f"NIT: {item['nit']} | {item['name']}")
        
    print("\n=== DIRECCIONES FALTANTES ===")
    for item in missing_addresses[:5]:
        print(f"NIT: {item['nit']} | {item['name']}")
        
    print("\n=== CUENTAS BANCARIAS FALTANTES ===")
    for item in missing_banks[:5]:
        print(f"NIT: {item['nit']} | {item['name']}")
        
    print(f"\nTOTAL_MISSING: {len(missing_info)}")
