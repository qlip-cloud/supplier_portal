from qp_supplier_front.services.get_data import get_supplier
APPROVE = "Aprobado"
from qp_supplier_front.constant.endpoint import SUPPLIER_INSERT, SUPPLIER_UPDATE, SUPPLIER_FIND
from qp_supplier_front.services.get_data import get_party, get_dynamic_link, get_bank_accounts
from qp_supplier_front.services.utils import add_log
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.www.information.index import get_is_alpla_admin

import frappe
import json
def handler(supplier_id):
    
    assert_that_user_has_permission()
    
    supplier = get_supplier(supplier_id)
    
    assert_that_supplier_is_pre_approved(supplier)
    
    supplier.qp_status = APPROVE
    
    sync_supplier(supplier)
    
    supplier.save()

    from qp_supplier_front.services.snapshot import clear_snapshot
    clear_snapshot(supplier_id)

    return {
        "supplier": supplier
    }

def assert_that_supplier_is_pre_approved(supplier):
    
    if not supplier.qp_preapproved:
        
        frappe.throw("El proveedor debe ser pre aprobado, para poder realizar esta accion")

def assert_that_user_has_permission():
    
    user = frappe.session.user

    user_roles = frappe.get_roles(user)
     
    if not get_is_alpla_admin(user_roles, "Alpla Finanzas"):
        
        frappe.throw("No tiene permiso para realizar esta funcion")  
    
def sync_supplier(supplier):
    
    payload = get_payload(supplier)
    
    is_gp_supplier = get_is_gp_supplier(supplier)
    
    endpoint = SUPPLIER_UPDATE if is_gp_supplier else SUPPLIER_INSERT
    
    result = send_request(endpoint, payload = payload)
    
    add_log("Create Supplier", payload, result, supplier.name)
    
    if ("status" in result and result.get("status") == 200):
        
        frappe.log_error(message=result.get("errors"), title=f"Error sync supplier: {supplier.name}")    
        
        frappe.throw(result.get("title"))
        
    if "result" in result and "statuscode" in result.get("result") and result.get("result").get("statuscode") != 200:
       
        frappe.log_error(message=result.get("result").get("description"), title=f"Error sync supplier: {supplier.name}")

def get_is_gp_supplier(supplier):
    
    result = send_request(SUPPLIER_FIND, param = f"{supplier.tax_id}")
    
    return result and "status" in result and result.get("status") == 200
         
def get_payload(supplier):
    
    busness_type = {
        "1": "2",
        "2": "1"
    }
    party = get_party(supplier)
    
    addresses = get_dynamic_link(supplier, "Address")
    
    address = get_address(addresses[0] if addresses else None)
    
    eft_information = get_eft_information(supplier)
    
    contact = get_contact(supplier)
    
    ciiu = frappe.get_doc("qp_CO_CIIU", party.ciiu_id)
        
    return {
        "vendorId": supplier.tax_id,
        "firstName": "",
        "middleName": "",
        "firstSurname": "",
        "secondSurname": "",
        "name": supplier.supplier_name,
        "nit": supplier.tax_id,
        "documentType": party.id_type_id,
        "businessType": party.business_type,
        "phone": party.phone_number,
        "phone2": "",
        "phone3": "",
        "landlinePhone": "",
        "address": {
            "country": address.get("country"),
            "state": address.get("state", ""),
            "city": address.get("municipality",""),
            "address": address.get("address_line1",""),
            "CoDCity": address.get("municipality_code", "")
        },
        "mail": get_contact_mail(contact),
        "regime": party.tax_regime,
        "nature": busness_type[party.business_type_id] if party.business_type_id else 0,
        "ciiu": ciiu.ciiu_id,
        "eftInformation": {
            "AccountType": eft_information.get("account_type",""),
            "AccountNumber":eft_information.get("bank_account_no",""),
            "RegulatoryCode2":eft_information.get("qp_routing_code",""),
            "bankName": eft_information.get("bank_name",""),
            "ibanCode": eft_information.get("qp_iban_number",""),
            "swiftCode": eft_information.get("qp_swift_number",""),
            "abaCode": eft_information.get("qp_aba_number", "")
        }
    }
def get_contact(supplier):
    
    contacts = get_dynamic_link(supplier, "Contact")

    contact = [contact for contact in contacts if contact.is_primary_contact and contact.user]
    if contact:
        return contact[0]

    contact = [contact for contact in contacts if contact.is_primary_contact]
    if contact:
        return contact[0]

    contact = [contact for contact in contacts if contact.user]
    if contact:
        return contact[0]

    return contacts[0] if contacts else None
    

def get_contact_mail(contact):
    if contact:
         if contact.user:
              return contact.user
         if contact.email_ids:
             return contact.email_ids[0].email_id
    return ""
    
def get_address(address):
    
    state_name = ""
    state_code = ""
    municipality_name = ""
    
    municipality_code = "00000"
    
    country = ""
    address_line1 = ""
    if address:
        
        country_name = address.country
        if country_name and not frappe.db.exists('Country', country_name):
            resolved_country = frappe.db.get_value('Country',
                {'country_name': country_name}, 'name'
            )
            if resolved_country:
                country_name = resolved_country
        country = frappe.db.get_value('Country', country_name, 'gp_country')
        address_line1 = address.address_line1
    if country == "Colombia":
        
        municipality_code = ""
        state_name_key = None
        
        if address.city:
            
            state_code_found = frappe.db.get_value('qp_CO_State', address.city, 'state_code')
            if state_code_found:
                state_code = state_code_found
                state_name_key = address.city
                state_doc = frappe.get_doc('qp_CO_State', address.city)
                state_name = state_doc.state_name
            else:
                # Fallback: buscar por state_name (datos legacy con nombre plano)
                state_fallback = frappe.db.get_value('qp_CO_State',
                    {'state_name': address.city}, ['name', 'state_name', 'state_code'], as_dict=True
                )
                if state_fallback:
                    state_name = state_fallback.state_name
                    state_code = state_fallback.state_code
                    state_name_key = state_fallback.name
            
        if address.state:
            
            mun_code_found = frappe.db.get_value('qp_CO_Municipality', address.state, 'municipality_code')
            if mun_code_found:
                municipality_code = mun_code_found
                mun_doc = frappe.get_doc('qp_CO_Municipality', address.state)
                municipality_name = mun_doc.municipality_name
            else:
                # Fallback: buscar por municipality_name (datos legacy con nombre plano)
                filters = {'municipality_name': address.state}
                if state_name_key:
                    filters['state_code'] = state_name_key
                mun_fallback = frappe.db.get_value('qp_CO_Municipality',
                    filters, ['municipality_name', 'municipality_code'], as_dict=True
                )
                if mun_fallback:
                    municipality_name = mun_fallback.municipality_name
                    municipality_code = mun_fallback.municipality_code
                
        municipality_code = f"{state_code}{municipality_code}"
        
    return {
        "state": state_name,
        "municipality": municipality_name,
        "municipality_code": municipality_code,
        "country":country,
        "address_line1":address_line1
    }
        
def get_eft_information(supplier):
    
    bank_accounts = get_bank_accounts(supplier, "Bank Account")
    
    account_type_dict = {
        "Corriente": 1,
        "Ahorro": 2
    }
    
    qp_iban_number = ""
    qp_swift_number = ""
    qp_aba_number = ""
    account_type= 0
    bank_name = ""
    qp_routing_code = ""
    bank_account_no = ""
    
    if bank_accounts:
        
        bank_account = bank_accounts[0]
        
        qp_iban_number = bank_account.qp_iban_number or ""
        
        bank = frappe.get_doc("Bank", bank_account.bank)
        
        qp_swift_number = bank.qp_swift_number or ""
        qp_aba_number = bank.qp_aba_number or ""
        bank_name = bank.bank_name or ""
        account_type= account_type_dict[bank_account.account_type] if bank_account.account_type  else 0
        bank_account_no = bank_account.bank_account_no or ""
        qp_routing_code = bank_account.qp_routing_code or ""
        
    return {
        "qp_iban_number": qp_iban_number,
        "qp_swift_number": qp_swift_number,
        "qp_aba_number": qp_aba_number,
        "account_type": account_type,
        "bank_name": bank_name,
        "qp_routing_code": qp_routing_code,
        "bank_account_no": bank_account_no,
    }