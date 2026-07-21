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

FIELD_TO_TAB = {
    # Basic
    "supplier_name": "basic",
    "id_type_name": "basic",
    "tax_id": "basic",
    "phone_number": "basic",
    "business_type_name": "basic",
    "qp_is_foreigner_supplier": "basic",
    # Legal
    "qp_legal_name": "legal",
    "qp_legal_id_type": "legal",
    "qp_legal_tax_id": "legal",
    "qp_legal_place_expedition": "legal",
    "qp_legal_date_expedition": "legal",
    # Bank account complement (same tab as list)
    "qp_public_resource_management": "bank_account",
    "qp_public_activity": "bank_account",
    "qp_public_recognition": "bank_account",
    "qp_link_politically_exposed": "bank_account",
    "qp_detail_politically_exposed": "bank_account",
    # Tax
    "qp_vat_officer": "tax",
    "tax_regime": "tax",
    "qp_industry_and_commerce_tax": "tax",
    "qp_industry_and_commerce_rate": "tax",
    "qp_self_retaining": "tax",
    "qp_resolution_self_retaining": "tax",
    "qp_major_contributor": "tax",
    "qp_resolution": "tax",
    "qp_vat_withholding_agent": "tax",
    "ciiu_id": "tax",
    # Financial
    "qp_financial_assets": "financial",
    "qp_financial_liabilities": "financial",
    "qp_financial_equity": "financial",
    "qp_financial_other_income": "financial",
    "qp_financial_monthly_income": "financial",
    "qp_financial_monthly_expenses": "financial",
    "qp_financial_details_income": "financial",
    # International
    "qp_financial_currency_foreigner": "international",
    "qp_financial_which_currency_foreigner": "international",
    "qp_financial_other_operations": "international",
    "qp_financial_item_foreigner": "international",
    "qp_financial_account_currency_foreigner": "international",
    "qp_financial_item_type": "international",
    "qp_financial_item_number": "international",
    "qp_financial_entity": "international",
    "qp_financial_amount": "international",
    "qp_financial_city": "international",
    "qp_financial_country": "international",
    "qp_financial_currency": "international",
    # Document
    "qp_has_quality_cert": "document",
    "qp_quality_cert_detail": "document",
}

def compare_snapshot_with_current(supplier_id):
    """
    Compara el snapshot activo con la información actual y retorna
    los campos modificados, pestañas con cambios, y detalle de ítems modificados.
    """
    snapshot_doc = frappe.get_all("qp_SP_SupplierSnapshot",
                                  filters={"supplier_id": supplier_id, "is_active": 1},
                                  fields=["snapshot_data"],
                                  order_by="creation desc",
                                  limit=1)
    if not snapshot_doc:
        return {}, [], {}

    try:
        snapshot = frappe.parse_json(snapshot_doc[0].snapshot_data)
    except Exception:
        return {}, [], {}

    current = get_supplier_data_dict(supplier_id)

    modified_fields = {}
    modified_tabs = set()
    modified_items = {}
    documents_modified = False

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
            modified_fields["file_id_{}".format(doc_id)] = "Archivo modificado o nuevo"
            modified_fields["link-{}".format(doc_id)] = "Archivo modificado o nuevo"
            modified_fields[doc_id] = "Modificado"
            documents_modified = True

    if documents_modified:
        modified_tabs.add("document")

    # 4. Comparar Direcciones (Tab 2)
    snap_addrs = snapshot.get("addresses", [])
    curr_addrs = current.get("addresses", [])
    addr_changes = _get_list_changes(snap_addrs, curr_addrs, ["address_line1", "address_line2", "city", "state", "country"])
    if addr_changes:
        modified_tabs.add("address")
        modified_items["address"] = addr_changes

    # 5. Comparar Contactos (Tab 3)
    snap_contacts = snapshot.get("contacts", [])
    curr_contacts = current.get("contacts", [])
    contact_changes = _get_list_changes(snap_contacts, curr_contacts, ["first_name", "qp_contact_type", "email_id", "phone"])
    if contact_changes:
        modified_tabs.add("contact")
        modified_items["contact"] = contact_changes

    # 6. Comparar Cuentas Bancarias (Tab 5)
    snap_banks = snapshot.get("bank_accounts", [])
    curr_banks = current.get("bank_accounts", [])
    bank_changes = _get_list_changes(snap_banks, curr_banks, ["bank", "bank_account_no", "account_type", "currency", "qp_iban_number", "qp_routing_code"])
    if bank_changes:
        modified_tabs.add("bank_account")
        modified_items["bank_account"] = bank_changes

    # 7. Comparar Accionistas (Tab 9)
    snap_sh = snapshot.get("shareholders", [])
    curr_sh = current.get("shareholders", [])
    sh_changes = _get_list_changes(snap_sh, curr_sh, ["fullname", "nationality", "have_resident_another_country", "have_american_visa", "id_type", "tax_id", "market_share"])
    if sh_changes:
        modified_tabs.add("shareholder")
        modified_items["shareholder"] = sh_changes

    # 8. Mapear campos modificados a sus tabs (para tabs de formulario no lista)
    for field_name in modified_fields:
        if field_name.startswith("file_id_") or field_name.startswith("link-"):
            modified_tabs.add("document")
            continue
        tab_name = FIELD_TO_TAB.get(field_name)
        if tab_name:
            modified_tabs.add(tab_name)

    return modified_fields, list(modified_tabs), modified_items

def clear_snapshot(supplier_id):
    """
    Desactiva los snapshots activos de este proveedor.
    """
    frappe.db.set_value("qp_SP_SupplierSnapshot", {"supplier_id": supplier_id, "is_active": 1}, "is_active", 0)
    frappe.db.commit()

def _get_list_changes(old_list, new_list, fields_to_compare):
    """
    Compara dos listas de items y retorna una lista con los cambios detallados.

    Cada cambio: {"name": str, "changes": {field: old_value}, "type": "modified"|"added"|"removed"}
    """
    result = []

    old_dict = {item["name"]: item for item in old_list if "name" in item}
    new_dict = {item["name"]: item for item in new_list if "name" in item}

    has_all_names = (len(old_dict) == len(old_list) and
                     len(new_dict) == len(new_list) and
                     old_dict and new_dict)

    if not has_all_names:
        # Comparación posicional para items sin nombre persistente
        max_len = max(len(old_list), len(new_list))
        for i in range(max_len):
            item_changes = {}
            is_new = False
            is_removed = False

            if i >= len(old_list):
                is_new = True
            elif i >= len(new_list):
                is_removed = True
            else:
                for f in fields_to_compare:
                    old_v = old_list[i].get(f)
                    new_v = new_list[i].get(f)
                    if str(new_v or "").strip() != str(old_v or "").strip():
                        item_changes[f] = old_v if old_v not in [None, ""] else "Ninguno"

            name = new_list[i].get("name") if not is_removed and i < len(new_list) else (
                old_list[i].get("name") if i < len(old_list) else "pos_{}".format(i)
            )
            if is_new:
                result.append({"name": name, "changes": item_changes or {}, "type": "added"})
            elif is_removed:
                result.append({"name": old_list[i].get("name", "pos_{}".format(i)), "changes": {}, "type": "removed"})
            elif item_changes:
                result.append({"name": name, "changes": item_changes, "type": "modified"})
        return result

    # Comparación por nombre
    for name, new_item in new_dict.items():
        if name not in old_dict:
            result.append({"name": name, "changes": {}, "type": "added"})
            continue
        old_item = old_dict[name]
        item_changes = {}
        for f in fields_to_compare:
            new_v = new_item.get(f)
            old_v = old_item.get(f)
            if str(new_v or "").strip() != str(old_v or "").strip():
                item_changes[f] = old_v if old_v not in [None, ""] else "Ninguno"
        if item_changes:
            result.append({"name": name, "changes": item_changes, "type": "modified"})

    for name in old_dict:
        if name not in new_dict:
            result.append({"name": name, "changes": {}, "type": "removed"})

    return result
