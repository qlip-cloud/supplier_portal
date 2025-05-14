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
    
    busness_type = {
        "1": "2",
        "2": "1"
    }
    party = get_party(supplier)
    
    #addresses = get_dynamic_link(supplier, "Address")
    
    bank_accounts = get_bank_accounts(supplier, "Bank Account")
    
    contacts = get_dynamic_link(supplier, "Contact")
    
    ciiu = frappe.get_doc("qp_CO_CIIU", party.ciiu_id)
    state = ""
    municipality_code = ""
    
    country = frappe.db.get_value('Country', party.country, 'gp_country')
    
    if country == "Colombia":
        
        state = frappe.db.get_value('qp_CO_State', party.state, 'state_id')
        municipality = frappe.db.get_value('qp_CO_Municipality', party.municipality, 'municipality_id')
        municipality_code = f"{state}{municipality}" if (state and state != "Otro") and (municipality and municipality) != "Otro" else ""
    
    payload ={
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
            "country": country,
            "state": state or "",
            "city": municipality_code,
            "address": party.address
        },
        "mail": contacts[0].user,
        "regime": party.tax_regime,
        "nature": busness_type[party.business_type_id] if party.business_type_id else 0,
        "ciiu": ciiu.ciiu_id,
        "eftInformation": {
            "bankName": "890903938",
            "ibanCode": bank_accounts[0].iban if bank_accounts and bank_accounts[0].iban else "",
            "swiftCode": "",
            "abaCode": ""
        }
    }

    result = send_request(SUPPLIER_INSERT, payload = payload)
    
    add_log("Create Supplier", payload, result, supplier.name)
    
    if ("status" in result and result.get("status") == 200):
        
        frappe.log_error(message=result.get("errors"), title=f"Error sync supplier: {supplier.name}")    
        
        frappe.throw(result.get("title"))
        
    if "result" in result and "statuscode" in result.get("result") and result.get("result").get("statuscode") != 200:
       
        frappe.log_error(message=result.get("result").get("description"), title=f"Error sync supplier: {supplier.name}")