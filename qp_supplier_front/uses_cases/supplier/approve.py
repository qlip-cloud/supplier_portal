from qp_supplier_front.services.get_data import get_supplier
APPROVE = "Aprobado"
from qp_supplier_front.constant.endpoint import SUPPLIER_INSERT
from qp_supplier_front.services.get_data import get_party, get_dynamic_link, get_bank_accounts
from qp_supplier_front.services.utils import add_log
from qp_authorization.use_case.bearer.authorize import send_request
import frappe
import json
def handler(supplier_id):
    
    supplier = get_supplier(supplier_id)
    
    supplier.qp_status = APPROVE
    
    sync_supplier(supplier)
    
    supplier.save()

    return {
        "supplier": supplier
    }
    
def sync_supplier(supplier):
    
    payload = get_payload(supplier)
    
    result = send_request(SUPPLIER_INSERT, payload = payload)
    
    add_log("Create Supplier", payload, result, supplier.name)
    
    if ("status" in result and result.get("status") == 200):
        
        frappe.log_error(message=result.get("errors"), title=f"Error sync supplier: {supplier.name}")    
        
        frappe.throw(result.get("title"))
        
    if "result" in result and "statuscode" in result.get("result") and result.get("result").get("statuscode") != 200:
       
        frappe.log_error(message=result.get("result").get("description"), title=f"Error sync supplier: {supplier.name}")
        
def get_payload(supplier):
    
    busness_type = {
        "1": "2",
        "2": "1"
    }
    party = get_party(supplier)
    
    address = get_address(party)
    
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
            "address": party.address,
            "CoDCity": address.get("municipality_code", "")
        },
        "mail": contact.user,
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
    
    return contact[0] if contact else ""
    
def get_address(party):
    
    state = ""
    municipality = ""
    municipality_code = "00000"
    
    country = frappe.db.get_value('Country', party.country, 'gp_country')
    
    if country == "Colombia":
        
        state = frappe.db.get_value('qp_CO_State', party.state,  "state_name")
        municipality = frappe.db.get_value('qp_CO_Municipality', party.municipality, 'municipality_name')
        
        municipality_code = f"{party.state_code}{party.municipality_code}"
        
    return {
        "state": state,
        "municipality": municipality,
        "municipality_code": municipality_code,
        "country":country
    }
        
def get_eft_information(supplier):
    
    bank_accounts = get_bank_accounts(supplier, "Bank Account")
    
    account_type_dict = {
        "Ahorro": 1,
        "Corriente": 2,
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