# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from qp_supplier_front.services.get_data import get_supplier, get_party, get_dynamic_link, get_bank_accounts

def get_supplier_data_dict(supplier_id):
    """
    Captura y serializa la información actual del proveedor, incluyendo party, direcciones,
    contactos, cuentas bancarias, accionistas y documentos adjuntos.
    """
    supplier = get_supplier(supplier_id)
    if not supplier:
        return {}

    # 1. Campos directos del Supplier
    supplier_fields = [
        "supplier_name", "qp_is_foreigner_supplier",
        "qp_legal_name", "qp_legal_id_type", "qp_legal_tax_id", "qp_legal_place_expedition", "qp_legal_date_expedition",
        "qp_financial_assets", "qp_financial_liabilities", "qp_financial_equity",
        "qp_financial_details_income", "qp_financial_monthly_income", "qp_financial_monthly_expenses", "qp_financial_other_income",
        "qp_financial_currency_foreigner", "qp_financial_which_currency_foreigner", "qp_financial_other_operations",
        "qp_financial_item_foreigner", "qp_financial_account_currency_foreigner", "qp_financial_item_type",
        "qp_financial_item_number", "qp_financial_entity", "qp_financial_amount", "qp_financial_city", "qp_financial_country", "qp_financial_currency",
        "qp_has_quality_cert", "qp_quality_cert_detail",
        "qp_vat_officer", "qp_industry_and_commerce_tax", "qp_industry_and_commerce_rate",
        "qp_self_retaining", "qp_resolution_self_retaining", "qp_major_contributor", "qp_resolution", "qp_vat_withholding_agent"
    ]
    supplier_data = {}
    for field in supplier_fields:
        supplier_data[field] = supplier.get(field)

    # 2. Campos del Party (qp_CO_ThirdParty)
    party = get_party(supplier)
    party_data = {}
    if party:
        party_fields = ["id_type", "tax_id", "phone_number", "business_type", "tax_regime", "ciiu_id"]
        for field in party_fields:
            party_data[field] = party.get(field)

    # 3. Direcciones
    addresses = get_dynamic_link(supplier, "Address")
    address_fields = ["address_title", "address_type", "address_line1", "address_line2", "city", "state", "country", "email_id", "phone"]
    addresses_data = []
    for addr in addresses:
        addr_dict = {"name": addr.name}
        for field in address_fields:
            addr_dict[field] = addr.get(field)
        addresses_data.append(addr_dict)

    # 4. Contactos
    contacts = get_dynamic_link(supplier, "Contact")
    contacts_data = []
    for ctc in contacts:
        ctc_dict = {
            "name": ctc.name,
            "first_name": ctc.first_name,
            "qp_contact_type": ctc.qp_contact_type,
            "email_id": ctc.email_ids[0].email_id if ctc.email_ids else "",
            "phone": ctc.phone_nos[0].phone if ctc.phone_nos else ""
        }
        contacts_data.append(ctc_dict)

    # 5. Cuentas Bancarias
    bank_accounts = get_bank_accounts(supplier, "Bank Account")
    bank_fields = ["bank", "bank_account_no", "account_type", "currency", "qp_iban_number", "qp_routing_code"]
    bank_accounts_data = []
    for acc in bank_accounts:
        acc_dict = {"name": acc.name}
        for field in bank_fields:
            acc_dict[field] = acc.get(field)
        bank_accounts_data.append(acc_dict)

    # 6. Accionistas
    shareholders_data = []
    for sh in supplier.get("qp_shareholders") or []:
        sh_dict = {
            "name": sh.name,
            "fullname": sh.fullname,
            "nationality": sh.nationality,
            "have_resident_another_country": sh.have_resident_another_country,
            "have_american_visa": sh.have_american_visa,
            "id_type": sh.id_type,
            "tax_id": sh.tax_id,
            "market_share": sh.market_share
        }
        shareholders_data.append(sh_dict)

    # 7. Documentos
    documents_data = {}
    for doc_line in supplier.get("qp_documents") or []:
        if doc_line.get("is_valid") or doc_line.get("file"):
            documents_data[doc_line.documento_setting] = doc_line.file

    return {
        "supplier": supplier_data,
        "party": party_data,
        "addresses": addresses_data,
        "contacts": contacts_data,
        "bank_accounts": bank_accounts_data,
        "shareholders": shareholders_data,
        "documents": documents_data
    }

def create_snapshot(supplier_id):
    """
    Crea un nuevo snapshot activo de la información del proveedor
    y desactiva los snapshots anteriores.
    """
    # Desactivar snapshots anteriores
    frappe.db.set_value("qp_SP_SupplierSnapshot", {"supplier_id": supplier_id, "is_active": 1}, "is_active", 0)

    data = get_supplier_data_dict(supplier_id)
    
    snapshot = frappe.get_doc({
        "doctype": "qp_SP_SupplierSnapshot",
        "supplier_id": supplier_id,
        "snapshot_data": frappe.as_json(data),
        "is_active": 1
    })
    snapshot.insert(ignore_permissions=True)
    frappe.db.commit()

def compare_snapshot_with_current(supplier_id):
    """
    Compara el snapshot activo con la información actual y retorna
    los campos y pestañas modificadas.
    """
    snapshot_doc = frappe.get_all("qp_SP_SupplierSnapshot",
                                  filters={"supplier_id": supplier_id, "is_active": 1},
                                  fields=["snapshot_data"],
                                  order_by="creation desc",
                                  limit=1)
    if not snapshot_doc:
        return {}, []

    try:
        snapshot = frappe.parse_json(snapshot_doc[0].snapshot_data)
    except Exception:
        return {}, []

    current = get_supplier_data_dict(supplier_id)

    modified_fields = {}
    modified_tabs = set()

    # 1. Comparar Supplier
    snap_sup = snapshot.get("supplier", {})
    curr_sup = current.get("supplier", {})
    for k, v in curr_sup.items():
        old_v = snap_sup.get(k)
        if str(v or "").strip() != str(old_v or "").strip():
            modified_fields[k] = old_v if old_v not in [None, ""] else "Ninguno"

    # 2. Comparar Party
    snap_party = snapshot.get("party", {})
    curr_party = current.get("party", {})
    party_mapping = {
        "id_type": "id_type_name",
        "tax_id": "tax_id",
        "phone_number": "phone_number",
        "business_type": "business_type_name",
        "tax_regime": "tax_regime",
        "ciiu_id": "ciiu_id"
    }
    for p_field, form_name in party_mapping.items():
        v = curr_party.get(p_field)
        old_v = snap_party.get(p_field)
        if str(v or "").strip() != str(old_v or "").strip():
            modified_fields[form_name] = old_v if old_v not in [None, ""] else "Ninguno"

    # 3. Comparar Documentos
    snap_docs = snapshot.get("documents", {})
    curr_docs = current.get("documents", {})
    for doc_setting, file_path in curr_docs.items():
        old_file = snap_docs.get(doc_setting)
        if file_path != old_file:
            doc_id = doc_setting.replace(" ", "-")
            modified_fields[f"file_id_{doc_id}"] = "Archivo modificado o nuevo"
            modified_fields[f"link-{doc_id}"] = "Archivo modificado o nuevo"
            modified_fields[doc_id] = "Modificado"

    # 4. Comparar Direcciones (Tab 2)
    snap_addrs = snapshot.get("addresses", [])
    curr_addrs = current.get("addresses", [])
    if _has_list_changes(snap_addrs, curr_addrs, ["address_line1", "address_line2", "city", "state", "country"]):
        modified_tabs.add("address")

    # 5. Comparar Contactos (Tab 3)
    snap_contacts = snapshot.get("contacts", [])
    curr_contacts = current.get("contacts", [])
    if _has_list_changes(snap_contacts, curr_contacts, ["first_name", "qp_contact_type", "email_id", "phone"]):
        modified_tabs.add("contact")

    # 6. Comparar Cuentas Bancarias (Tab 5)
    snap_banks = snapshot.get("bank_accounts", [])
    curr_banks = current.get("bank_accounts", [])
    if _has_list_changes(snap_banks, curr_banks, ["bank", "bank_account_no", "account_type", "currency", "qp_iban_number", "qp_routing_code"]):
        modified_tabs.add("bank_account")

    # 7. Comparar Accionistas (Tab 9)
    snap_sh = snapshot.get("shareholders", [])
    curr_sh = current.get("shareholders", [])
    if _has_list_changes(snap_sh, curr_sh, ["fullname", "nationality", "have_resident_another_country", "have_american_visa", "id_type", "tax_id", "market_share"]):
        modified_tabs.add("shareholder")

    return modified_fields, list(modified_tabs)

def clear_snapshot(supplier_id):
    """
    Desactiva los snapshots activos de este proveedor.
    """
    frappe.db.set_value("qp_SP_SupplierSnapshot", {"supplier_id": supplier_id, "is_active": 1}, "is_active", 0)
    frappe.db.commit()

def _has_list_changes(old_list, new_list, fields_to_compare):
    if len(old_list) != len(new_list):
        return True

    old_dict = {item["name"]: item for item in old_list if "name" in item}
    new_dict = {item["name"]: item for item in new_list if "name" in item}

    if len(old_dict) != len(old_list) or len(new_dict) != len(new_list):
        # Si no tienen IDs persistentes o coincidencia directa, comparación posicional simple
        for i in range(len(old_list)):
            for f in fields_to_compare:
                if str(old_list[i].get(f) or "").strip() != str(new_list[i].get(f) or "").strip():
                    return True
        return False

    for name, new_item in new_dict.items():
        if name not in old_dict:
            return True
        old_item = old_dict[name]
        for f in fields_to_compare:
            if str(new_item.get(f) or "").strip() != str(old_item.get(f) or "").strip():
                return True

    for name in old_dict:
        if name not in new_dict:
            return True

    return False
