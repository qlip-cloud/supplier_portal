import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import SUPPLIER_ALL, SUPPLIER_ALL_DATETIME
from qp_supplier_front.services.bank_resolver import resolve_bank_name

from datetime import datetime

current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
owner = "Administrator"

# Mapeo inverso al de approve.py: {int_servicio: string_frappe}
ACCOUNT_TYPE_MAP = {1: "Corriente", 2: "Ahorro"}


def fetch_suppliers_from_api(sync_datetime) -> tuple:
    """
    Obtiene la respuesta de proveedores desde el endpoint externo.
    Retorna una tupla (result_dict, nuevo_sync_datetime).
    """
    if not sync_datetime:
        result = send_request(SUPPLIER_ALL)
        return result, None
    else:
        now_dt = datetime.now()
        format_datetime = now_dt.strftime("%Y-%m-%dT%H:%M:%S")
        result = send_request(SUPPLIER_ALL_DATETIME, param=format_datetime)
        return result, now_dt


def get_existing_tax_ids(vendor_ids: list) -> list:
    """
    Obtiene la lista de tax_ids de proveedores existentes en la base de datos.
    """
    if not vendor_ids:
        return []
    return frappe.db.get_list(
        'Supplier',
        filters={'tax_id': ["in", vendor_ids]},
        pluck='tax_id'
    )


def resolve_and_create_banks(suppliers_response: list, existing_tax_ids: list) -> dict:
    """
    Fase 1: Recolectar todos los eftInformation de proveedores nuevos
    y resolver sus bancos en lote. Retorna un diccionario mapping de vendor_id a la lista de EFTs resueltos.
    """
    eft_by_vendor = {}  # {vendor_id: [eft_data_resuelto, ...]}

    for supplier_response in suppliers_response:
        vendor_id = supplier_response.get('vendorId')

        if vendor_id in existing_tax_ids:
            continue

        eft_list = supplier_response.get('eftInformation') or []
        if not eft_list:
            continue

        resolved_efts = []
        for eft in eft_list:
            if not eft:
                continue

            raw_bank_name = (eft.get('bankName', '') or '').strip()
            swift_code = (eft.get('swiftCode', '') or '').strip()

            if not raw_bank_name:
                continue

            resolved_bank = resolve_bank_name(raw_bank_name, swift_code)

            # Si el banco no existe, crearlo
            if not frappe.db.exists("Bank", resolved_bank):
                new_bank = frappe.new_doc("Bank")
                new_bank.bank_name = resolved_bank
                if swift_code:
                    new_bank.qp_swift_number = swift_code
                aba_code = (eft.get('abaCode', '') or '').strip()
                if aba_code:
                    new_bank.qp_aba_number = aba_code
                new_bank.insert(ignore_permissions=True)
                frappe.db.commit()

            resolved_efts.append({
                'bank': resolved_bank,
                'account_type': ACCOUNT_TYPE_MAP.get(eft.get('accountType'), ''),
                'account_no': (eft.get('accountNumber', '') or '').strip(),
                'iban': (eft.get('ibanCode', '') or '').strip(),
                'swift': swift_code,
                'aba': (eft.get('abaCode', '') or '').strip(),
                'regulatory_code': (eft.get('regulatoryCode2', '') or '').strip(),
            })

        if resolved_efts:
            eft_by_vendor[vendor_id] = resolved_efts

    return eft_by_vendor


def create_supplier_record(vendor_id: str, name: str) -> tuple:
    """Construye la tupla de datos para el DocType Supplier."""
    return (
        vendor_id, name, vendor_id,
        "Todos los grupos de proveedores", "SUP-.YYYY.-",
        current_time, current_time, owner, owner
    )


def create_contact_records(supplier_index: int, vendor_id: str, name: str, mail: str) -> tuple:
    """Construye las tuplas para Contact y su Dynamic Link correspondiente."""
    contact_name = f"{supplier_index}-{vendor_id}"
    contact = (
        contact_name, name, mail,
        current_time, current_time, owner, owner
    )
    dynamic_link = (
        contact_name, "Supplier", vendor_id,
        "Contact", contact_name,
        current_time, current_time, owner, owner
    )
    return contact, dynamic_link


def create_address_records(address_index: int, vendor_id: str, address_data: dict) -> tuple:
    """Construye las tuplas para Address y su Dynamic Link correspondiente."""
    type_address = frappe._("Billing")
    address_name = f"{address_index}-{vendor_id}:{type_address}"
    address = (
        address_name,
        address_data['address'], address_data['city'], address_data['state'], address_data['country'],
        "Billing",
        current_time, current_time, owner, owner
    )
    dynamic_link = (
        address_name, "Supplier", vendor_id,
        "Address", address_name,
        current_time, current_time, owner, owner
    )
    return address, dynamic_link


def create_bank_account_record(vendor_id: str, eft_index: int, eft_data: dict) -> tuple:
    """Construye la tupla de datos para el DocType Bank Account."""
    account_name = f"{vendor_id}:{eft_data['account_no']}"
    is_default = 1 if eft_index == 0 else 0
    return (
        account_name,
        account_name,
        eft_data['bank'],
        eft_data['account_type'],
        eft_data['account_no'],
        "Supplier",
        vendor_id,
        is_default,
        eft_data['iban'] or None,
        eft_data['regulatory_code'] or None,
        current_time, current_time, owner, owner
    )


def build_records(suppliers_response: list, existing_tax_ids: list, eft_by_vendor: dict) -> dict:
    """
    Fase 2: Construir los registros de proveedores, contactos y direcciones en tuplas utilizando funciones atómicas.
    """
    suppliers = []
    contacts = []
    addresses = []
    dynamic_links = []
    bank_accounts = []

    # Copiamos existing_tax_ids localmente para evitar side effects
    local_tax_ids = list(existing_tax_ids)

    for supplier_index, supplier_response in enumerate(suppliers_response):
        vendor_id = supplier_response.get('vendorId')
        if not vendor_id or vendor_id in local_tax_ids:
            continue

        name = supplier_response['name']
        mail = supplier_response.get('mail', '')

        suppliers.append(create_supplier_record(vendor_id, name))

        if mail and mail.strip():
            contact, dynamic_link = create_contact_records(supplier_index, vendor_id, name, mail)
            contacts.append(contact)
            dynamic_links.append(dynamic_link)

        for address_index, address_data in enumerate(supplier_response.get('address', [])):
            address, dynamic_link = create_address_records(address_index, vendor_id, address_data)
            addresses.append(address)
            dynamic_links.append(dynamic_link)

        # Agregar Bank Accounts resueltas para este proveedor
        for eft_index, eft_data in enumerate(eft_by_vendor.get(vendor_id, [])):
            bank_accounts.append(create_bank_account_record(vendor_id, eft_index, eft_data))

        local_tax_ids.append(vendor_id)

    return {
        "suppliers": suppliers,
        "contacts": contacts,
        "addresses": addresses,
        "dynamic_links": dynamic_links,
        "bank_accounts": bank_accounts
    }



def bulk_insert_suppliers(suppliers: list) -> None:
    """Inserta en lote los registros de Supplier."""
    if suppliers:
        frappe.db.bulk_insert(
            "Supplier",
            ["name", "supplier_name", "tax_id", "supplier_group", "naming_series", "creation", "modified", "owner", "modified_by"],
            suppliers
        )


def bulk_insert_contacts(contacts: list) -> None:
    """Inserta en lote los registros de Contact."""
    if contacts:
        frappe.db.bulk_insert(
            "Contact",
            ["name", "first_name", "user", "creation", "modified", "owner", "modified_by"],
            contacts
        )


def bulk_insert_addresses(addresses: list) -> None:
    """Inserta en lote los registros de Address."""
    if addresses:
        frappe.db.bulk_insert(
            "Address",
            ["name", "address_line1", "city", "state", "country", "address_type", "creation", "modified", "owner", "modified_by"],
            addresses
        )


def bulk_insert_dynamic_links(dynamic_links: list) -> None:
    """Inserta en lote los registros de Dynamic Link."""
    if dynamic_links:
        frappe.db.bulk_insert(
            "Dynamic Link",
            ["name", "link_doctype", "link_name", "parenttype", "parent", "creation", "modified", "owner", "modified_by"],
            dynamic_links
        )


def bulk_insert_bank_accounts(bank_accounts: list) -> None:
    """Inserta en lote los registros de Bank Account."""
    if bank_accounts:
        frappe.db.bulk_insert(
            "Bank Account",
            [
                "name", "account_name", "bank", "account_type", "bank_account_no",
                "party_type", "party", "is_default",
                "qp_iban_number", "qp_routing_code",
                "creation", "modified", "owner", "modified_by"
            ],
            bank_accounts
        )


def bulk_insert_all_records(records: dict) -> None:
    """
    Fase 3: INSERT batch de todos los registros acumulados utilizando funciones de inserción atómicas.
    """
    bulk_insert_suppliers(records.get("suppliers", []))
    bulk_insert_contacts(records.get("contacts", []))
    bulk_insert_addresses(records.get("addresses", []))
    bulk_insert_dynamic_links(records.get("dynamic_links", []))
    bulk_insert_bank_accounts(records.get("bank_accounts", []))



@frappe.whitelist()
def handler():
    sync_datetime = frappe.db.get_single_value('qp_SP_MasterSetup', 'supplier_date_sync')

    result, nuevo_sync_datetime = fetch_suppliers_from_api(sync_datetime)

    if result:
        suppliers_response = result.get('vendors', [])
        vendor_ids = [s.get('vendorId') for s in suppliers_response if s.get('vendorId')]
        existing_tax_ids = get_existing_tax_ids(vendor_ids)

        eft_by_vendor = resolve_and_create_banks(suppliers_response, existing_tax_ids)
        records = build_records(suppliers_response, existing_tax_ids, eft_by_vendor)

        if nuevo_sync_datetime:
            sync_datetime = nuevo_sync_datetime

        bulk_insert_all_records(records)

    frappe.db.set_value('qp_SP_MasterSetup', None, 'supplier_date_sync', sync_datetime)

