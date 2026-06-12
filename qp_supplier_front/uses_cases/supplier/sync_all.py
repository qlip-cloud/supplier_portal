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


def get_existing_suppliers(vendor_ids: list) -> dict:
    """
    Obtiene un diccionario {tax_id: name} de los proveedores existentes.
    """
    if not vendor_ids:
        return {}
    suppliers = frappe.db.get_all(
        'Supplier',
        filters={'tax_id': ["in", vendor_ids]},
        fields=['tax_id', 'name']
    )
    return {s['tax_id']: s['name'] for s in suppliers}


def get_suppliers_with_contacts(supplier_names: list) -> set:
    """
    Obtiene un conjunto con los nombres de proveedores que ya tienen un contacto asociado.
    """
    if not supplier_names:
        return set()
    links = frappe.db.sql("""
        SELECT dl.link_name 
        FROM `tabDynamic Link` dl
        INNER JOIN `tabContact` c ON dl.parent = c.name
        WHERE dl.link_doctype = 'Supplier' 
          AND dl.link_name IN %s
          AND dl.parenttype = 'Contact'
    """, (supplier_names,), as_dict=False)
    return {l[0] for l in links} if links else set()


def get_suppliers_with_addresses(supplier_names: list) -> set:
    """
    Obtiene un conjunto con los nombres de proveedores que ya tienen una dirección asociada.
    """
    if not supplier_names:
        return set()
    links = frappe.db.sql("""
        SELECT dl.link_name 
        FROM `tabDynamic Link` dl
        INNER JOIN `tabAddress` a ON dl.parent = a.name
        WHERE dl.link_doctype = 'Supplier' 
          AND dl.link_name IN %s
          AND dl.parenttype = 'Address'
    """, (supplier_names,), as_dict=False)
    return {l[0] for l in links} if links else set()


def get_suppliers_with_bank_accounts(supplier_names: list) -> set:
    """
    Obtiene un conjunto con los nombres de proveedores que ya tienen una cuenta bancaria asociada.
    """
    if not supplier_names:
        return set()
    accounts = frappe.db.get_all(
        'Bank Account',
        filters={
            'party_type': 'Supplier',
            'party': ['in', supplier_names]
        },
        pluck='party'
    )
    return set(accounts)





def resolve_and_create_banks(suppliers_response: list) -> dict:
    """
    Fase 1: Recolectar todos los eftInformation de proveedores
    y resolver sus bancos en lote de forma deduplicada.
    Retorna un diccionario mapping de vendor_id a la lista de EFTs resueltos.
    """
    eft_by_vendor = {}  # {vendor_id: [eft_data_resuelto, ...]}

    # 1. Recolectar todos los pares únicos (raw_bank_name, swift_code) en el lote
    unique_banks = set()
    for supplier_response in suppliers_response:
        eft_list = supplier_response.get('eftInformation') or []
        for eft in eft_list:
            if not eft:
                continue
            raw_bank_name = (eft.get('bankName', '') or '').strip()
            swift_code = (eft.get('swiftCode', '') or '').strip()
            if raw_bank_name:
                unique_banks.add((raw_bank_name, swift_code))

    # 2. Resolver y crear en orden. Al hacerlo secuencialmente sobre un catálogo
    #    que se actualiza y comitea al instante, se previene la duplicación.
    resolved_mapping = {}  # {(raw_bank_name, swift_code): resolved_bank_name}

    for raw_bank_name, swift_code in sorted(unique_banks):
        resolved_bank = resolve_bank_name(raw_bank_name, swift_code)

        # Si el banco no existe en la base de datos, crearlo
        if not frappe.db.exists("Bank", resolved_bank):
            new_bank = frappe.new_doc("Bank")
            new_bank.bank_name = resolved_bank
            if swift_code:
                new_bank.qp_swift_number = swift_code
            
            # Buscar el primer eft correspondiente para extraer el abaCode si existe
            aba_code = ""
            for supplier_item in suppliers_response:
                for eft in (supplier_item.get('eftInformation') or []):
                    if eft and (eft.get('bankName', '') or '').strip() == raw_bank_name and (eft.get('swiftCode', '') or '').strip() == swift_code:
                        aba_code = (eft.get('abaCode', '') or '').strip()
                        break
                if aba_code:
                    break

            if aba_code:
                new_bank.qp_aba_number = aba_code
            new_bank.insert(ignore_permissions=True)
            frappe.db.commit()

        resolved_mapping[(raw_bank_name, swift_code)] = resolved_bank

    # 3. Construir el mapeo eft_by_vendor utilizando resolved_mapping
    for supplier_response in suppliers_response:
        vendor_id = supplier_response.get('vendorId')
        if not vendor_id:
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

            resolved_bank = resolved_mapping.get((raw_bank_name, swift_code))
            if not resolved_bank:
                continue

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


def build_records(
    suppliers_response: list,
    existing_suppliers: dict,
    suppliers_with_contacts: set,
    suppliers_with_addresses: set,
    suppliers_with_bank_accounts: set,
    eft_by_vendor: dict
) -> dict:
    """
    Fase 2: Construir los registros de proveedores, contactos y direcciones en tuplas utilizando funciones atómicas.
    """
    suppliers = []
    contacts = []
    addresses = []
    dynamic_links = []
    bank_accounts = []

    # Copiamos localmente para evitar side effects y mejorar performance
    local_tax_ids = set(existing_suppliers.keys())
    local_suppliers_with_contacts = set(suppliers_with_contacts)
    local_suppliers_with_addresses = set(suppliers_with_addresses)
    local_suppliers_with_bank_accounts = set(suppliers_with_bank_accounts)

    for supplier_index, supplier_response in enumerate(suppliers_response):
        vendor_id = supplier_response.get('vendorId')
        if not vendor_id:
            continue

        name = supplier_response['name']
        mail = supplier_response.get('mail', '')

        # Si el proveedor ya existe en la base de datos
        if vendor_id in local_tax_ids:
            supplier_name = existing_suppliers.get(vendor_id)
            if supplier_name:
                # 1. Contacto
                if mail and mail.strip() and supplier_name not in local_suppliers_with_contacts:
                    contact, dynamic_link = create_contact_records(supplier_index, supplier_name, name, mail)
                    contacts.append(contact)
                    dynamic_links.append(dynamic_link)
                    local_suppliers_with_contacts.add(supplier_name)

                # 2. Direcciones
                if supplier_name not in local_suppliers_with_addresses:
                    address_list = supplier_response.get('address', [])
                    for address_index, address_data in enumerate(address_list):
                        address, dynamic_link = create_address_records(address_index, supplier_name, address_data)
                        addresses.append(address)
                        dynamic_links.append(dynamic_link)
                    if address_list:
                        local_suppliers_with_addresses.add(supplier_name)

                # 3. Cuentas bancarias
                if supplier_name not in local_suppliers_with_bank_accounts:
                    bank_list = eft_by_vendor.get(vendor_id, [])
                    for eft_index, eft_data in enumerate(bank_list):
                        bank_accounts.append(create_bank_account_record(supplier_name, eft_index, eft_data))
                    if bank_list:
                        local_suppliers_with_bank_accounts.add(supplier_name)
            continue

        suppliers.append(create_supplier_record(vendor_id, name))

        if mail and mail.strip():
            contact, dynamic_link = create_contact_records(supplier_index, vendor_id, name, mail)
            contacts.append(contact)
            dynamic_links.append(dynamic_link)
            if vendor_id not in local_suppliers_with_contacts:
                local_suppliers_with_contacts.add(vendor_id)

        for address_index, address_data in enumerate(supplier_response.get('address', [])):
            address, dynamic_link = create_address_records(address_index, vendor_id, address_data)
            addresses.append(address)
            dynamic_links.append(dynamic_link)

        # Agregar Bank Accounts resueltas para este proveedor
        for eft_index, eft_data in enumerate(eft_by_vendor.get(vendor_id, [])):
            bank_accounts.append(create_bank_account_record(vendor_id, eft_index, eft_data))

        local_tax_ids.add(vendor_id)

    return {
        "suppliers": suppliers,
        "contacts": contacts,
        "addresses": addresses,
        "dynamic_links": dynamic_links,
        "bank_accounts": bank_accounts
    }




def bulk_insert_suppliers(suppliers: list) -> None:
    """Inserta en lote los registros de Supplier, evitando duplicados en la lista y base de datos."""
    if suppliers:
        unique_suppliers = {s[0]: s for s in suppliers}
        filtered_suppliers = list(unique_suppliers.values())
        names = [s[0] for s in filtered_suppliers]
        existing_names = frappe.db.get_all("Supplier", filters={"name": ["in", names]}, pluck="name")
        filtered = [s for s in filtered_suppliers if s[0] not in existing_names]
        if filtered:
            frappe.db.bulk_insert(
                "Supplier",
                ["name", "supplier_name", "tax_id", "supplier_group", "naming_series", "creation", "modified", "owner", "modified_by"],
                filtered
            )


def bulk_insert_contacts(contacts: list) -> None:
    """Inserta en lote los registros de Contact, evitando duplicados en la lista y base de datos."""
    if contacts:
        unique_contacts = {c[0]: c for c in contacts}
        filtered_contacts = list(unique_contacts.values())
        names = [c[0] for c in filtered_contacts]
        existing_names = frappe.db.get_all("Contact", filters={"name": ["in", names]}, pluck="name")
        filtered = [c for c in filtered_contacts if c[0] not in existing_names]
        if filtered:
            frappe.db.bulk_insert(
                "Contact",
                ["name", "first_name", "user", "creation", "modified", "owner", "modified_by"],
                filtered
            )


def bulk_insert_addresses(addresses: list) -> None:
    """Inserta en lote los registros de Address, evitando duplicados en la lista y base de datos."""
    if addresses:
        unique_addresses = {a[0]: a for a in addresses}
        filtered_addresses = list(unique_addresses.values())
        names = [a[0] for a in filtered_addresses]
        existing_names = frappe.db.get_all("Address", filters={"name": ["in", names]}, pluck="name")
        filtered = [a for a in filtered_addresses if a[0] not in existing_names]
        if filtered:
            frappe.db.bulk_insert(
                "Address",
                ["name", "address_line1", "city", "state", "country", "address_type", "creation", "modified", "owner", "modified_by"],
                filtered
            )


def bulk_insert_dynamic_links(dynamic_links: list) -> None:
    """Inserta en lote los registros de Dynamic Link, evitando duplicados en la lista y base de datos."""
    if dynamic_links:
        unique_links = {dl[0]: dl for dl in dynamic_links}
        filtered_links = list(unique_links.values())
        names = [dl[0] for dl in filtered_links]
        existing_names = frappe.db.get_all("Dynamic Link", filters={"name": ["in", names]}, pluck="name")
        filtered = [dl for dl in filtered_links if dl[0] not in existing_names]
        if filtered:
            frappe.db.bulk_insert(
                "Dynamic Link",
                ["name", "link_doctype", "link_name", "parenttype", "parent", "creation", "modified", "owner", "modified_by"],
                filtered
            )


def bulk_insert_bank_accounts(bank_accounts: list) -> None:
    """Inserta en lote los registros de Bank Account, evitando duplicados en la lista y base de datos."""
    if bank_accounts:
        unique_accounts = {ba[0]: ba for ba in bank_accounts}
        filtered_accounts = list(unique_accounts.values())
        names = [ba[0] for ba in filtered_accounts]
        existing_names = frappe.db.get_all("Bank Account", filters={"name": ["in", names]}, pluck="name")
        filtered = [ba for ba in filtered_accounts if ba[0] not in existing_names]
        if filtered:
            frappe.db.bulk_insert(
                "Bank Account",
                [
                    "name", "account_name", "bank", "account_type", "bank_account_no",
                    "party_type", "party", "is_default",
                    "qp_iban_number", "qp_routing_code",
                    "creation", "modified", "owner", "modified_by"
                ],
                filtered
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
        existing_suppliers = get_existing_suppliers(vendor_ids)
        supplier_names = list(existing_suppliers.values())
        
        suppliers_with_contacts = get_suppliers_with_contacts(supplier_names)
        suppliers_with_addresses = get_suppliers_with_addresses(supplier_names)
        suppliers_with_bank_accounts = get_suppliers_with_bank_accounts(supplier_names)

        eft_by_vendor = resolve_and_create_banks(suppliers_response)
        records = build_records(
            suppliers_response,
            existing_suppliers,
            suppliers_with_contacts,
            suppliers_with_addresses,
            suppliers_with_bank_accounts,
            eft_by_vendor
        )

        if nuevo_sync_datetime:
            sync_datetime = nuevo_sync_datetime

        bulk_insert_all_records(records)

    frappe.db.set_value('qp_SP_MasterSetup', None, 'supplier_date_sync', sync_datetime)



