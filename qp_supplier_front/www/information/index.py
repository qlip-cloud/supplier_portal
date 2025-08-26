import frappe
from qp_supplier_front.services.get_data import get_party, get_supplier, get_document_types, get_business_types, get_dynamic_link,get_bank_accounts, get_regimes, get_ciius

def get_context(context):
    
    context.no_cache = 1
    
    party = None
    
    supplier = None
    
    supplier_id = None
    
    query_params = frappe.request.args
    
    supplier_id = query_params.get("supplier")
    
    if supplier_id:
        
        supplier = get_supplier(supplier_id)
    
        party = get_party(supplier)
        
        context.addresses = get_dynamic_link(supplier, "Address")
    
        contacts = get_dynamic_link(supplier, "Contact")
        
        context.contacts =contacts
        
        context.bank_accounts = get_bank_accounts(supplier, "Bank Account")
        
        document_settings = setup_document_settings(supplier.qp_documents)
    
        context.document_settings = document_settings
        
        user = frappe.session.user
        
        user_roles = frappe.get_roles(user)
    
        context.is_alpla_admin = "Alpla Administrator" in user_roles
    
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
  
def setup_document_settings(qp_documents):
    
    document_settings = frappe.get_list("qp_SP_DocumentSetting", filters = {"is_active": 1}, fields = ["name", "title", "is_required", "is_active"])
    
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

