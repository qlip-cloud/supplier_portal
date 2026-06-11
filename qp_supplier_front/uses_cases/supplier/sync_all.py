import frappe
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import SUPPLIER_ALL, SUPPLIER_ALL_DATETIME
from qp_supplier_front.services.bank_resolver import resolve_bank_name

from datetime import datetime

current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
owner = "Administrator"

# Mapeo inverso al de approve.py: {int_servicio: string_frappe}
ACCOUNT_TYPE_MAP = {1: "Corriente", 2: "Ahorro"}


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
        bank_accounts = []
        count = 0

        existing_tax_ids = frappe.db.get_list(
            'Supplier',
            filters={'tax_id': ["in", [s.get('vendorId') for s in suppliers_response]]},
            pluck='tax_id'
        )

        # ------------------------------------------------------------------
        # Fase 1: Recolectar todos los eftInformation de proveedores nuevos
        # y resolver sus bancos en lote antes de cualquier insert.
        # Un banco puede ser compartido por N proveedores; solo se crea una vez.
        # ------------------------------------------------------------------
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

                raw_bank_name = eft.get('bankName', '') or ''
                raw_bank_name = raw_bank_name.strip()
                swift_code = eft.get('swiftCode', '') or ''
                swift_code = swift_code.strip()

                if not raw_bank_name:
                    continue

                # resolve_bank_name puede crear un banco nuevo si no hay match.
                # Al estar en el loop de resolución (antes del INSERT batch),
                # bancos duplicados en este mismo lote se resuelven automáticamente
                # porque resolve_bank_name usa frappe.db.exists en Nivel 1.
                resolved_bank = resolve_bank_name(raw_bank_name, swift_code)

                # Si el banco no existe, crearlo ahora (una sola vez por nombre único)
                if not frappe.db.exists("Bank", resolved_bank):
                    new_bank = frappe.new_doc("Bank")
                    new_bank.bank_name = resolved_bank
                    if swift_code:
                        new_bank.qp_swift_number = swift_code
                    aba_code = eft.get('abaCode', '').strip()
                    if aba_code:
                        new_bank.qp_aba_number = aba_code
                    new_bank.insert(ignore_permissions=True)
                    frappe.db.commit()

                resolved_efts.append({
                    'bank': resolved_bank,
                    'account_type': ACCOUNT_TYPE_MAP.get(eft.get('accountType'), ''),
                    'account_no': eft.get('accountNumber', '').strip(),
                    'iban': eft.get('ibanCode', '').strip(),
                    'swift': swift_code,
                    'aba': eft.get('abaCode', '').strip(),
                    'regulatory_code': eft.get('regulatoryCode2', '').strip(),
                })

            if resolved_efts:
                eft_by_vendor[vendor_id] = resolved_efts

        # ------------------------------------------------------------------
        # Fase 2: Construir los registros de proveedores, contactos y direcciones
        # ------------------------------------------------------------------
        for supplier_index, supplier_response in enumerate(suppliers_response):

            if supplier_response.get('vendorId') in existing_tax_ids:
                count += 1
                continue

            vendor_id = supplier_response['vendorId']
            name = supplier_response['name']
            mail = supplier_response.get('mail', '')

            suppliers.append((
                vendor_id, name, vendor_id,
                "Todos los grupos de proveedores", "SUP-.YYYY.-",
                current_time, current_time, owner, owner
            ))

            if mail and mail.strip():

                contact_name = f"{supplier_index}-{vendor_id}"

                contacts.append((
                    contact_name, name, mail,
                    current_time, current_time, owner, owner
                ))

                dynamic_links.append((
                    contact_name, "Supplier", vendor_id,
                    "Contact", contact_name,
                    current_time, current_time, owner, owner
                ))

            for address_index, address_data in enumerate(supplier_response.get('address', [])):

                type_address = frappe._("Billing")

                address_name = f"{address_index}-{vendor_id}:{type_address}"

                addresses.append((
                    address_name,
                    address_data['address'], address_data['city'], address_data['state'], address_data['country'],
                    "Billing",
                    current_time, current_time, owner, owner
                ))

                dynamic_links.append((
                    address_name, "Supplier", vendor_id,
                    "Address", address_name,
                    current_time, current_time, owner, owner
                ))

            # Agregar Bank Accounts resueltas para este proveedor
            for eft_index, eft_data in enumerate(eft_by_vendor.get(vendor_id, [])):

                account_name = f"{vendor_id}:{eft_data['account_no']}"
                is_default = 1 if eft_index == 0 else 0

                bank_accounts.append((
                    account_name,
                    account_name,          # account_name field
                    eft_data['bank'],
                    eft_data['account_type'],
                    eft_data['account_no'],
                    "Supplier",
                    vendor_id,
                    is_default,
                    eft_data['iban'] or None,
                    eft_data['regulatory_code'] or None,
                    current_time, current_time, owner, owner
                ))

            existing_tax_ids.append(vendor_id)

    frappe.db.set_value('qp_SP_MasterSetup', None, 'supplier_date_sync', sync_datetime)

    # ------------------------------------------------------------------
    # Fase 3: INSERT batch de todos los registros acumulados
    # ------------------------------------------------------------------
    if suppliers:
        frappe.db.bulk_insert(
            "Supplier",
            ["name", "supplier_name", "tax_id", "supplier_group", "naming_series", "creation", "modified", "owner", "modified_by"],
            suppliers
        )

    if contacts:
        frappe.db.bulk_insert(
            "Contact",
            ["name", "first_name", "user", "creation", "modified", "owner", "modified_by"],
            contacts
        )

    if addresses:
        frappe.db.bulk_insert(
            "Address",
            ["name", "address_line1", "city", "state", "country", "address_type", "creation", "modified", "owner", "modified_by"],
            addresses
        )

    if dynamic_links:
        frappe.db.bulk_insert(
            "Dynamic Link",
            ["name", "link_doctype", "link_name", "parenttype", "parent", "creation", "modified", "owner", "modified_by"],
            dynamic_links
        )

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
