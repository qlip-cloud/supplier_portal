"""
supplier_strategy.py (GP)
==========================
Estrategia de sincronizacion de proveedores para GP.
Define endpoints, construccion de payload, deteccion de existencia
y validacion de respuesta especificos de GP.
"""

import frappe
from qp_supplier_front.services.get_data import get_party, get_dynamic_link, get_bank_accounts
from qp_supplier_front.constant.endpoint import SUPPLIER_FIND, SUPPLIER_INSERT, SUPPLIER_UPDATE


def build_gp_supplier_payload(supplier):
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
            "city": address.get("municipality", ""),
            "address": address.get("address_line1", ""),
            "CoDCity": address.get("municipality_code", "")
        },
        "mail": contact.user,
        "regime": party.tax_regime,
        "nature": busness_type[party.business_type_id] if party.business_type_id else 0,
        "ciiu": ciiu.ciiu_id,
        "eftInformation": {
            "AccountType": eft_information.get("account_type", ""),
            "AccountNumber": eft_information.get("bank_account_no", ""),
            "RegulatoryCode2": eft_information.get("qp_routing_code", ""),
            "bankName": eft_information.get("bank_name", ""),
            "ibanCode": eft_information.get("qp_iban_number", ""),
            "swiftCode": eft_information.get("qp_swift_number", ""),
            "abaCode": eft_information.get("qp_aba_number", "")
        }
    }


def get_contact(supplier):
    contacts = get_dynamic_link(supplier, "Contact")

    contact = [contact for contact in contacts if contact.is_primary_contact and contact.user]

    return contact[0] if contact else ""


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
                filters = {'municipality_name': address.state}
                if state_name_key:
                    filters['state_code'] = state_name_key
                mun_fallback = frappe.db.get_value('qp_CO_Municipality',
                    filters, ['municipality_name', 'municipality_code'], as_dict=True
                )
                if mun_fallback:
                    municipality_name = mun_fallback.municipality_name
                    municipality_code = mun_fallback.municipality_code

        municipality_code = "{}{}".format(state_code, municipality_code)

    return {
        "state": state_name,
        "municipality": municipality_name,
        "municipality_code": municipality_code,
        "country": country,
        "address_line1": address_line1
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
    account_type = 0
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
        account_type = account_type_dict[bank_account.account_type] if bank_account.account_type else 0
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


def is_gp_found(response):
    return response and "status" in response and response.get("status") == 200


def validate_gp_response(response, supplier_name, log_error_fn, throw_fn):
    if "status" in response and response.get("status") == 200:
        log_error_fn(message=response.get("errors"), title="Error sync supplier: {}".format(supplier_name))
        throw_fn(response.get("title"))

    if "result" in response and "statuscode" in response.get("result") and response.get("result").get("statuscode") != 200:
        log_error_fn(message=response.get("result").get("description"), title="Error sync supplier: {}".format(supplier_name))


GP_SUPPLIER_STRATEGY = {
    "name": "GP",
    "endpoints": {
        "find": SUPPLIER_FIND,
        "insert": SUPPLIER_INSERT,
        "update": SUPPLIER_UPDATE,
    },
    "build_payload": build_gp_supplier_payload,
    "is_found": is_gp_found,
    "validate_response": validate_gp_response,
}
