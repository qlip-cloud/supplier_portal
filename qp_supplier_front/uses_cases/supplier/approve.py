from qp_supplier_front.services.get_data import get_supplier
APPROVE = "Aprobado"
from qp_supplier_front.constant.endpoint import SUPPLIER_INSERT
from qp_supplier_front.services.get_data import get_party, get_dynamic_link
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
    
    contacts = get_dynamic_link(supplier, "Contact")
    
    payload ={
        "vendorId": supplier.name,
        "name": supplier.supplier_name,
        "documentType": party.id_type_id,
        "businessType": party.business_type,
        "phone": party.phone_number,
        "phone2": "",
        "phone3": "",
        "address": {
            "country": addresses[0].country,
            "state": addresses[0].state,
            "city": addresses[0].city,
            "address": addresses[0].address_line1
        },
        "mail": contacts[0].user,
        "regime": party.tax_regime,
        "ciiu": party.ciiu_id
    }
    
    result = send_request(SUPPLIER_INSERT, payload = payload)
    
