import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import SUPPLIER_ALL, SUPPLIER_ALL_DATETIME
from qp_supplier_front.services.bank_resolver import resolve_bank_name

from datetime import datetime

current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
owner = "Administrator"

# Mapeo inverso al de approve.py: {int_servicio: string_frappe}
ACCOUNT_TYPE_MAP = {1: "Corriente", 2: "Ahorro"}


def fetch_suppliers_from_api(sync_datetime):
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


def get_existing_tax_ids(vendor_ids: list):
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


def get_existing_suppliers(vendor_ids: list):
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


def get_existing_address_count(supplier_names):
    """
    Retorna {supplier_name: cantidad_de_direcciones} contando Dynamic Links.
    """
    if not supplier_names:
        return {}
    rows = frappe.db.sql("""
        SELECT dl.link_name, COUNT(*) as cnt
        FROM `tabDynamic Link` dl
        INNER JOIN `tabAddress` a ON dl.parent = a.name
        WHERE dl.link_doctype = 'Supplier'
          AND dl.link_name IN %s
          AND dl.parenttype = 'Address'
        GROUP BY dl.link_name
    """, (supplier_names,), as_dict=True)
    return {r.link_name: r.cnt for r in rows}




def resolve_and_create_banks(suppliers_response: list):
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


def create_supplier_record(vendor_id: str, name: str):
    """Construye la tupla de datos para el DocType Supplier."""
    return (
        vendor_id, name, vendor_id,
        "Todos los grupos de proveedores", "SUP-.YYYY.-",
        current_time, current_time, owner, owner
    )


def create_contact_records(supplier_index: int, vendor_id: str, name: str, mail: str, phone=""):
    """Construye las tuplas para Contact y su Dynamic Link correspondiente."""
    contact_name = f"{supplier_index}-{vendor_id}"
    contact = (
        contact_name, name, mail, phone,
        current_time, current_time, owner, owner
    )
    dynamic_link = (
        contact_name, "Supplier", vendor_id,
        "Contact", contact_name,
        current_time, current_time, owner, owner
    )
    return contact, dynamic_link


_RESOLVED_STATE_CACHE = {}
_RESOLVED_MUNICIPALITY_CACHE = {}


def _resolve_state_code(state_name):
    """Resuelve un nombre de departamento a su name (codigo) en qp_CO_State."""
    if not state_name:
        return "Otro-Otro"
    cache_key = state_name.strip().lower()
    if cache_key in _RESOLVED_STATE_CACHE:
        return _RESOLVED_STATE_CACHE[cache_key]
    state_doc = frappe.db.get_value("qp_CO_State",
        {"state_name": state_name.strip()},
        "name"
    )
    if not state_doc:
        state_doc = "Otro-Otro"
    _RESOLVED_STATE_CACHE[cache_key] = state_doc
    return state_doc


def _resolve_municipality_code(municipality_name, state_code):
    """Resuelve un nombre de municipio a su name (codigo) en qp_CO_Municipality."""
    if not municipality_name:
        return "Otro-Otro"
    cache_key = "{}|{}".format(municipality_name.strip().lower(), state_code or "")
    if cache_key in _RESOLVED_MUNICIPALITY_CACHE:
        return _RESOLVED_MUNICIPALITY_CACHE[cache_key]
    filters = {"municipality_name": municipality_name.strip()}
    if state_code:
        filters["state_code"] = state_code
    mun_doc = frappe.db.get_value("qp_CO_Municipality",
        filters,
        "name"
    )
    if not mun_doc:
        mun_doc = "Otro-Otro"
    _RESOLVED_MUNICIPALITY_CACHE[cache_key] = mun_doc
    return mun_doc


def create_address_records(address_index, vendor_id, address_data):
    """Construye las tuplas para Address y su Dynamic Link correspondiente."""
    type_address = frappe._("Billing")
    address_name = "{}-{}:{}".format(address_index, vendor_id, type_address)

    # Resolver codigos de departamento y municipio desde la API de GP
    gp_state = address_data.get('state', '')
    gp_city = address_data.get('city', '')

    resolved_state_code = _resolve_state_code(gp_state)
    resolved_city_code = _resolve_municipality_code(gp_city, resolved_state_code)

    address = (
        address_name,
        address_data['address'],
        resolved_state_code,       # city = qp_CO_State.name (departamento)
        resolved_city_code,        # state = qp_CO_Municipality.name (municipio)
        address_data['country'],
        "Billing",
        current_time, current_time, owner, owner
    )
    dynamic_link = (
        address_name, "Supplier", vendor_id,
        "Address", address_name,
        current_time, current_time, owner, owner
    )
    return address, dynamic_link


def create_bank_account_record(vendor_id: str, eft_index: int, eft_data: dict):
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
        1,  # qp_from_sync
        current_time, current_time, owner, owner
    )


def _delete_synced_addresses(supplier_name, vendor_id):
    """Elimina direcciones sincronizadas previamente (identificadas por patron de nombre)."""
    like_pattern = "%-{}:Billing".format(vendor_id)
    address_names = frappe.db.sql("""
        SELECT dl.parent
        FROM `tabDynamic Link` dl
        WHERE dl.link_doctype = 'Supplier'
          AND dl.link_name = %s
          AND dl.parenttype = 'Address'
          AND dl.parent LIKE %s
    """, (supplier_name, like_pattern), as_dict=False)
    if not address_names:
        return
    names = [a[0] for a in address_names]
    frappe.db.delete("Dynamic Link", {
        "parent": ["in", names],
        "parenttype": "Address"
    })
    frappe.db.delete("Address", {
        "name": ["in", names]
    })


def build_records(
    suppliers_response: list,
    existing_suppliers: dict,
    eft_by_vendor: dict,
    supplier_address_count=None,
    force_supplier=None
):
    """
    Fase 2: Construir los registros de proveedores, contactos y direcciones en tuplas utilizando funciones atómicas.
    """
    suppliers = []
    contacts = []
    addresses = []
    dynamic_links = []
    bank_accounts = []

    local_tax_ids = set(existing_suppliers.keys())

    for supplier_index, supplier_response in enumerate(suppliers_response):
        vendor_id = supplier_response.get('vendorId')
        if not vendor_id:
            continue

        name = supplier_response['name']
        mail = supplier_response.get('mail', '')
        phone = supplier_response.get('phone', '')

        # Si el proveedor ya existe en la base de datos
        if vendor_id in local_tax_ids:
            supplier_name = existing_suppliers.get(vendor_id)
            if supplier_name:
                # 1. Contacto (solo si tiene mail)
                if mail and mail.strip():
                    contact, dynamic_link = create_contact_records(supplier_index, vendor_id, name, mail, phone)
                    contacts.append(contact)
                    dynamic_links.append(dynamic_link[:2] + (supplier_name,) + dynamic_link[3:])

                # 2. Direcciones
                address_list = supplier_response.get('address', [])

                is_force = force_supplier and str(force_supplier) == str(vendor_id)
                if is_force:
                    _delete_synced_addresses(supplier_name, vendor_id)

                existing_count = (supplier_address_count or {}).get(supplier_name, 0)
                if is_force:
                    existing_count = 0

                for address_index, address_data in enumerate(address_list):
                    if address_index < existing_count:
                        continue
                    address, dynamic_link = create_address_records(address_index, vendor_id, address_data)
                    addresses.append(address)
                    dynamic_links.append(dynamic_link[:2] + (supplier_name,) + dynamic_link[3:])

                # 3. Cuentas bancarias
                bank_list = eft_by_vendor.get(vendor_id, [])
                for eft_index, eft_data in enumerate(bank_list):
                    account = create_bank_account_record(vendor_id, eft_index, eft_data)
                    bank_accounts.append(account[:6] + (supplier_name,) + account[7:])
            continue

        suppliers.append(create_supplier_record(vendor_id, name))

        if mail and mail.strip():
            contact, dynamic_link = create_contact_records(supplier_index, vendor_id, name, mail, phone)
            contacts.append(contact)
            dynamic_links.append(dynamic_link)

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




def bulk_insert_suppliers(suppliers: list):
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


def bulk_insert_contacts(contacts: list):
    """Inserta o actualiza registros de Contact usando upsert."""
    if not contacts:
        return
    unique = {c[0]: c for c in contacts}
    records = list(unique.values())
    columns = ["name", "first_name", "user", "mobile_no", "creation", "modified", "owner", "modified_by"]
    placeholders = ",".join(["%s"] * len(columns))
    values_placeholder = ",".join(["({})".format(placeholders)] * len(records))
    flat_values = []
    for rec in records:
        flat_values.extend(rec)
    frappe.db.sql("""
        INSERT INTO `tabContact`
            (`name`, `first_name`, `user`, `mobile_no`, `creation`, `modified`, `owner`, `modified_by`)
        VALUES {}
        ON DUPLICATE KEY UPDATE
            `first_name` = VALUES(`first_name`),
            `mobile_no` = VALUES(`mobile_no`),
            `modified` = VALUES(`modified`)
    """.format(values_placeholder), flat_values)


def bulk_insert_addresses(addresses: list):
    """Inserta o actualiza registros de Address usando upsert."""
    if not addresses:
        return
    unique = {a[0]: a for a in addresses}
    records = list(unique.values())
    columns = ["name", "address_line1", "city", "state", "country", "address_type", "creation", "modified", "owner", "modified_by"]
    placeholders = ",".join(["%s"] * len(columns))
    values_placeholder = ",".join(["({})".format(placeholders)] * len(records))
    flat_values = []
    for rec in records:
        flat_values.extend(rec)
    frappe.db.sql("""
        INSERT INTO `tabAddress`
            (`name`, `address_line1`, `city`, `state`, `country`, `address_type`, `creation`, `modified`, `owner`, `modified_by`)
        VALUES {}
        ON DUPLICATE KEY UPDATE
            `address_line1` = VALUES(`address_line1`),
            `city` = VALUES(`city`),
            `state` = VALUES(`state`),
            `country` = VALUES(`country`),
            `modified` = VALUES(`modified`)
    """.format(values_placeholder), flat_values)


def bulk_insert_dynamic_links(dynamic_links: list):
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


def bulk_insert_bank_accounts(bank_accounts: list):
    """Inserta o actualiza registros de Bank Account usando upsert."""
    if not bank_accounts:
        return
    unique = {ba[0]: ba for ba in bank_accounts}
    records = list(unique.values())
    columns = [
        "name", "account_name", "bank", "account_type", "bank_account_no",
        "party_type", "party", "is_default",
        "qp_iban_number", "qp_routing_code",
        "qp_from_sync",
        "creation", "modified", "owner", "modified_by"
    ]
    placeholders = ",".join(["%s"] * len(columns))
    values_placeholder = ",".join(["({})".format(placeholders)] * len(records))
    flat_values = []
    for rec in records:
        flat_values.extend(rec)
    frappe.db.sql("""
        INSERT INTO `tabBank Account`
            (`name`, `account_name`, `bank`, `account_type`, `bank_account_no`,
             `party_type`, `party`, `is_default`,
             `qp_iban_number`, `qp_routing_code`,
             `qp_from_sync`,
             `creation`, `modified`, `owner`, `modified_by`)
        VALUES {}
        ON DUPLICATE KEY UPDATE
            `bank` = VALUES(`bank`),
            `account_type` = VALUES(`account_type`),
            `bank_account_no` = VALUES(`bank_account_no`),
            `is_default` = VALUES(`is_default`),
            `qp_iban_number` = VALUES(`qp_iban_number`),
            `qp_routing_code` = VALUES(`qp_routing_code`),
            `modified` = VALUES(`modified`)
    """.format(values_placeholder), flat_values)




def bulk_insert_all_records(records: dict):
    """
    Fase 3: INSERT batch de todos los registros acumulados utilizando funciones de inserción atómicas.
    """
    bulk_insert_suppliers(records.get("suppliers", []))
    bulk_insert_contacts(records.get("contacts", []))
    bulk_insert_addresses(records.get("addresses", []))
    bulk_insert_dynamic_links(records.get("dynamic_links", []))
    bulk_insert_bank_accounts(records.get("bank_accounts", []))



@frappe.whitelist(allow_guest=True)
def handler():

    try:
        sync_datetime = frappe.db.get_single_value('qp_SP_MasterSetup', 'supplier_date_sync')
        force_supplier = frappe.request.args.get('force_supplier')

        result, nuevo_sync_datetime = fetch_suppliers_from_api(sync_datetime)

        if result:
            suppliers_response = result.get('vendors', [])
            vendor_ids = [s.get('vendorId') for s in suppliers_response if s.get('vendorId')]
            existing_suppliers = get_existing_suppliers(vendor_ids)
            supplier_names = list(existing_suppliers.values())
            supplier_address_count = get_existing_address_count(supplier_names)

            eft_by_vendor = resolve_and_create_banks(suppliers_response)
            records = build_records(
                suppliers_response,
                existing_suppliers,
                eft_by_vendor,
                supplier_address_count=supplier_address_count,
                force_supplier=force_supplier
            )

            if nuevo_sync_datetime:
                sync_datetime = nuevo_sync_datetime

            bulk_insert_all_records(records)

        frappe.db.set_value('qp_SP_MasterSetup', None, 'supplier_date_sync', sync_datetime)
    except Exception as error:

        frappe.log_error(message=frappe.get_traceback(), title="Error sync_all supplier")


