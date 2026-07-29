import frappe
from qp_supplier_front.services.get_data import get_party, get_supplier, get_document_types, get_business_types, get_dynamic_link, get_bank_accounts, get_regimes, get_ciius, has_recent_news, get_has_dispatch_permission

def get_context(context):
    
    context.no_cache = 1
    
    party = None
    
    supplier = None
    
    supplier_id = None
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    if supplier_id:
        
        try:
            supplier = get_supplier(supplier_id)
        except frappe.DoesNotExistError:
            frappe.local.flags.redirect_location = "/welcome?error=no_encontrado"
            raise frappe.Redirect
        
        user = frappe.session.user
        user_roles = frappe.get_roles(user)
        context.is_alpla_admin = get_is_alpla_admin(user_roles)
        
        if not context.is_alpla_admin:
            contact_name = frappe.get_value("Contact", {"user": user}, "name")
            if not contact_name:
                frappe.local.flags.redirect_location = "/welcome?error=sin_acceso"
                raise frappe.Redirect
            
            contact = frappe.get_doc("Contact", contact_name)
            is_allowed = any(
                link.link_doctype == "Supplier" and link.link_name == supplier_id
                for link in contact.links
            )
            if not is_allowed:
                frappe.local.flags.redirect_location = "/welcome?error=sin_acceso"
                raise frappe.Redirect
        
        party = get_party(supplier)
        
        context.addresses = get_dynamic_link(supplier, "Address")
    
        contacts = get_dynamic_link(supplier, "Contact")
        
        context.contacts = contacts
        
        primary_phone = None
        if contacts:
            for contact in contacts:
                phone = contact.mobile_no or (contact.phone_nos[0].phone if contact.phone_nos else None)
                if contact.is_primary_contact and phone:
                    primary_phone = phone
                    break
            if not primary_phone:
                for contact in contacts:
                    phone = contact.mobile_no or (contact.phone_nos[0].phone if contact.phone_nos else None)
                    if phone:
                        primary_phone = phone
                        if not contact.is_primary_contact:
                            for c in contacts:
                                if c.is_primary_contact:
                                    c.is_primary_contact = 0
                                    c.save()
                            contact.is_primary_contact = 1
                            contact.save()
                        break
        context.primary_phone = primary_phone
        
        context.bank_accounts = get_bank_accounts(supplier, "Bank Account")
        
        document_settings = setup_document_settings(supplier.qp_documents)
    
        context.document_settings = document_settings
        
        context.qp_preapproved = supplier.qp_preapproved
        
        context.is_preapproved = get_is_preapproved(user_roles, supplier.qp_preapproved)
        
        context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
        
        # Snapshot comparison for Alpla admin during review
        context.modified_fields = "{}"
        context.modified_tabs = "[]"
        context.modified_items = "{}"
        if supplier.qp_status == "En revisión" and context.is_alpla_admin:
            from qp_supplier_front.services.snapshot import compare_snapshot_with_current
            modified_fields, modified_tabs, modified_items = compare_snapshot_with_current(supplier_id)
            context.modified_fields = frappe.as_json(modified_fields)
            context.modified_tabs = frappe.as_json(modified_tabs)
            context.modified_items = frappe.as_json(modified_items)
        
    
    context.is_estatus_editable = (not supplier or supplier.qp_status not in ("En revisión", "Aprobado")) and not context.is_alpla_admin

    setup_document_types(context, party)
    
    setup_legal_document_types(context, supplier)
    
    setup_business_types(context, party)
    
    setup_regimes(context, party)
    
    setup_ciius(context, party)
    
    context.countries = frappe.get_all("Country", fields = ["name", "country_name"])
    
    context.cities = frappe.get_all("qp_CO_State", fields = ["name", "state_name"])
    
    context.states = frappe.get_all("qp_CO_Municipality", fields = ["name", "municipality_name"])
        
    context.banks = frappe.get_all("Bank", fields = ["name", "bank_name"])
    
    context.bank_account_types = frappe.get_all("Bank Account Type", fields = ["name", "account_type"])
    
    context.currencies = frappe.get_all("Currency", fields = ["name", "currency_name"])
    
    context.responses = [{
        "name":"",
        "value": "Respuesta"
        },{
        "name":"SI",
        "value": "SI"
        },{ 
        "name":"NO",
        "value": "NO"
        }]
    
    context.supplier = supplier
    
    context.party = party
    
    context.supplier_id = supplier_id

    config = frappe.get_single("qp_SP_MasterSetup")
    context.show_terms_conditions = config.show_terms_conditions
    context.terms_content = config.terms_content
    context.conditions_content = config.conditions_content

    context.has_recent_news = has_recent_news()
    
    setup_wizard_tabs(context)
     
def setup_wizard_tabs(context):
    
    sections = frappe.get_all(
        "qp_SP_FieldSection",
        filters={"is_active": 1},
        fields=["code", "tab_label", "tab_group", "tab_order", "show_in_wizard", "has_finish_button", "number_valid"],
        order_by="tab_order asc, creation asc"
    )
    
    TAB_LABEL_FALLBACK = {
        "basic": u"Informaci\u00f3n B\u00e1sica",
        "address": u"Direcciones",
        "contact": "Contactos",
        "legal": u"Representante Legal",
        "bank_account": u"Cuentas Bancarias",
        "bank_account_complement": u"Cuentas Bancarias",
        "tax": u"Informaci\u00f3n Tributaria",
        "financial": u"Informaci\u00f3n Financiera",
        "international": u"Operaciones Internacionales",
        "shareholder": u"Accionistas y Asociados",
        "document": "Documentos",
    }
    
    TEMPLATE_MAP = {
        "basic": "basic",
        "address": "address",
        "contact": "contact",
        "legal": "legal",
        "bank_account": "bank_account",
        "bank_account_complement": "bank_account",
        "tax": "tax",
        "financial": "financial",
        "international": "international",
        "shareholder": "shareholder",
        "document": "document",
    }
    
    groups = {}
    for s in sections:
        group = s.tab_group or s.code
        if group not in groups:
            groups[group] = {
                "sections": [],
                "show_in_wizard": False,
                "label": s.tab_label or TAB_LABEL_FALLBACK.get(s.code, s.code),
                "order": s.tab_order or 0,
                "has_finish_button": False,
                "templates": set(),
            }
        groups[group]["sections"].append(s)
        if s.show_in_wizard:
            groups[group]["show_in_wizard"] = True
            if s.tab_label:
                groups[group]["label"] = s.tab_label
            if s.tab_order:
                groups[group]["order"] = s.tab_order
            if s.has_finish_button:
                groups[group]["has_finish_button"] = True
        template = TEMPLATE_MAP.get(s.code)
        if template:
            groups[group]["templates"].add(template)
    
    wizard_tabs = []
    for group_key, group_data in groups.items():
        if not group_data["show_in_wizard"]:
            continue
        wizard_tabs.append({
            "key": group_key,
            "label": group_data["label"],
            "order": group_data["order"],
            "sections": [s.code for s in group_data["sections"]],
            "section_codes": " ".join(s.code for s in group_data["sections"]),
            "has_finish_button": group_data["has_finish_button"],
            "templates": sorted(group_data["templates"]),
        })
    
    wizard_tabs.sort(key=lambda t: t["order"])
    
    for idx, tab in enumerate(wizard_tabs):
        tab["tab_id"] = "tab{}".format(idx + 1)
        tab["prev_tab_id"] = wizard_tabs[idx - 1]["tab_id"] if idx > 0 else None
        tab["prev_tab_label"] = wizard_tabs[idx - 1]["label"] if idx > 0 else None
        tab["next_tab_id"] = wizard_tabs[idx + 1]["tab_id"] if idx < len(wizard_tabs) - 1 else None
        tab["next_tab_label"] = wizard_tabs[idx + 1]["label"] if idx < len(wizard_tabs) - 1 else None
    
    context.wizard_tabs = wizard_tabs
    
def get_is_alpla_admin(user_roles, add_rol = None, only_admin = False):
    
    admin_roles = {"Alpla Administrator", "Administrator"}
    
    if not only_admin:
        
        admin_roles |= {"Alpla Compras", "Alpla Finanzas"} if not add_rol else {add_rol}

    return not admin_roles.isdisjoint(user_roles)

def get_is_preapproved(user_roles, qp_preapproved):

    if not qp_preapproved:
        
        return get_is_alpla_admin(user_roles, "Alpla Compras")
        
        
    return get_is_alpla_admin(user_roles, "Alpla Finanzas")


def setup_document_settings(qp_documents):
    
    document_settings = frappe.get_list("qp_SP_DocumentSetting", filters = {"is_active": 1}, fields = ["name", "title", "is_required", "is_active"], order_by="creation asc")
    
    for document_setting in document_settings:
        
        values = [qp_document.as_dict() for qp_document in qp_documents if qp_document.documento_setting == document_setting.get("name") and qp_document.get("is_valid")]
        
        document_setting.setdefault("line", values[0] if values else None)
        
    return document_settings

def setup_regimes(context, party):
    
    regimes = get_regimes()
    
    if party:
    
        set_selected_select(regimes, party.tax_regime)
            
    context.regimes = regimes
    
def setup_ciius(context, party):
    
    ciius = get_ciius()
    
    if party:
    
        set_selected_select(ciius, party.ciiu_id)
            
    context.ciius = ciius
    
def setup_document_types(context, party):
    
    document_types = get_document_types()
    
    if party:
        
        set_selected_select(document_types, party.id_type)
            
    context.document_types = document_types
    
def setup_legal_document_types(context, supplier):
    
    legal_document_types = get_document_types()
    
    if supplier:
        
        set_selected_select(legal_document_types, supplier.qp_legal_id_type)
            
    context.legal_document_types = legal_document_types
    
def setup_business_types(context, party):
    
    business_types = get_business_types()
    
    if party:
    
        set_selected_select(business_types, party.business_type)
            
    context.business_types = business_types
    
    
def set_selected_select(select_list, code):
    
    for select in select_list:
        
        selected = ""
        
        if select.get("name") == code:
            
            selected = "selected"
        
        select.setdefault("selected", selected)

