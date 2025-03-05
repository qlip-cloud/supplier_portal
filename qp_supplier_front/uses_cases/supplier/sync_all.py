import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import SUPPLIER_ALL, SUPPLIER_ALL_DATETIME
from qp_supplier_front.uses_cases.information.basic.save import create_supplier
from qp_supplier_front.uses_cases.information.address.save import handler as save_address  
from qp_supplier_front.services.create_data import create_party, create_contact
 

from datetime import datetime
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
owner = "Administrator"

@frappe.whitelist()
def handler():
    
    
    sync_datetime = frappe.db.get_single_value('qp_SP_MasterSetup', 'supplier_date_sync')
    
    result = None
    
    if not sync_datetime:

        result = send_request(SUPPLIER_ALL)
        
    else:
        sync_datetime = datetime.now()
        
        format_datetime = sync_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        
        result = send_request(SUPPLIER_ALL_DATETIME, param=format_datetime)
        
    if (result):
        
        suppliers_response = result.get('vendors', [])
        suppliers = []
        contacts = []
        addresses = []
        dynamic_links = []
        count = 0
        tax_ids = frappe.db.get_list('Supplier', filters={'tax_id': ["in", [supplier_response.get('vendorId') for supplier_response in suppliers_response]]}, pluck='tax_id')
             
        for key, supplier_response in enumerate(suppliers_response):
            
            if supplier_response.get('vendorId') not in tax_ids:
                
                vendor_id = supplier_response['vendorId']
                name = supplier_response['name']
                mail = supplier_response.get('mail', '')

                suppliers.append((vendor_id, name, vendor_id, "Todos los grupos de proveedores", current_time, current_time, owner, owner))
                
                
                if mail and mail.strip():
                    
                    contact_name = f"{key}-{vendor_id}"
                    
                    contacts.append((contact_name, name, mail, current_time, current_time, owner, owner))

                    dynamic_links.append((contact_name, "Supplier", vendor_id, "Contact", contact_name, current_time, current_time, owner, owner))

                for key_address, address in enumerate(supplier_response['address']):
                    
                    type_address = frappe._("Billing")
                    
                    address_name = f"{key_address}-{vendor_id}:{type_address}"

                    addresses.append((address_name, address['address'], address['city'], address['state'], address['country'], "Billing", current_time, current_time, owner, owner))
                    
                    dynamic_links.append((address_name, "Supplier", vendor_id, "Address", address_name, current_time, current_time, owner, owner))
                    
                tax_ids.append(supplier_response.get('vendorId'))

            else:
                count += 1
                print(f"El proveedor con tax_id {supplier_response.get('vendorId')} ya existe en la base de datos en linea {key}")
                
        print(f"Se han creado {count} proveedores")
               
    frappe.db.set_value('qp_SP_MasterSetup', None, 'supplier_date_sync', sync_datetime)
    

    if suppliers:
        frappe.db.sql("""
            INSERT INTO `tabSupplier` (name, supplier_name, tax_id, supplier_group, creation, modified, owner, modified_by)
            VALUES {values}
        """.format(values=', '.join(str(supplier) for supplier in suppliers)))

    if contacts:
        frappe.db.sql("""
            INSERT INTO `tabContact` (name, first_name, user, creation, modified, owner, modified_by)
            VALUES {values}
        """.format(values=', '.join(str(contact) for contact in contacts)))

    if addresses:
        frappe.db.sql("""
            INSERT INTO `tabAddress` (name, address_line1, city, state, country, address_type, creation, modified, owner, modified_by)
            VALUES {values}
        """.format(values=', '.join(str(address) for address in addresses)))

    if dynamic_links:
        frappe.db.sql("""
            INSERT INTO `tabDynamic Link` (name, link_doctype, link_name, parenttype, parent, creation, modified, owner, modified_by)
            VALUES {values}
        """.format(values=', '.join(str(dynamic_link) for dynamic_link in dynamic_links)))
