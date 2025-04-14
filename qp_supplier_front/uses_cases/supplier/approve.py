from qp_supplier_front.services.get_data import get_supplier
APPROVE = "Aprobado"
from qp_supplier_front.constant.endpoint import SUPPLIER_INSERT
from qp_supplier_front.services.get_data import get_party, get_dynamic_link, get_bank_accounts
from qp_authorization.use_case.bearer.authorize import send_request

def handler(supplier_id):
    
    supplier = get_supplier(supplier_id)
    
    supplier.qp_status = APPROVE
    
    sync_supplier(supplier)
    
    supplier.save()

    return {
        "supplier": supplier
    }
    
def sync_supplier(supplier):
    
    party = get_party(supplier)
    
    addresses = get_dynamic_link(supplier, "Address")
    
    bank_accounts = get_bank_accounts(supplier, "Bank Account")
    
    contacts = get_dynamic_link(supplier, "Contact")
    
    payload ={
        "vendorId": supplier.name,
        "firstName": "",
        "middleName": "",
        "firstSurname": "",
        "secondSurname": "",
        "name": supplier.supplier_name,
        "nit": "string",
        "documentType": party.id_type_id,
        "businessType": party.business_type,
        "phone": party.phone_number,
        "phone2": "",
        "phone3": "",
        "landlinePhone": "string",
        "address": {
            "country": addresses[0].country,
            "state": addresses[0].state,
            "city": addresses[0].city,
            "address": addresses[0].address_line1
        },
        "mail": contacts[0].user,
        "regime": party.tax_regime,
        "nature": 0,
        "ciiu": party.ciiu_id,
        "eftInformation": {
            "bankName": "string",
            "ibanCode": "string",
            "swiftCode": "string",
            "abaCode": "string"
        }
    }
    
    result = send_request(SUPPLIER_INSERT, payload = payload)
    
