import frappe

def get_party(doc):
    
    doctype = "qp_CO_ThirdParty"
    
    filters = [
		["DocType Link", "link_doctype", "=", doc.doctype],
		["DocType Link", "link_fieldname", "=", doc.name],
		["DocType Link", "parenttype", "=", doctype],
	]
    
    links = frappe.get_all(doctype, filters=filters, fields=["*"])
    
    return frappe.get_doc(doctype, links[0].get("name")) if links else None

def get_dynamic_link(doc, doctype):
    
    
    filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", doctype]
	]
    
    all_data = frappe.get_all(doctype, filters=filters, fields=["*"], order_by = "creation desc")
    
    return [frappe.get_doc(doctype, data.get("name")) for data in all_data]

def get_bank_accounts(doc, doctype):
    
    filters = ["party_type", "=", doc.doctype], ["party", "=", doc.name]
    
    all_data = frappe.get_all(doctype, filters = filters , fields = ["name"])
    
    return [frappe.get_doc(doctype, data.get("name")) for data in all_data]
     
def get_supplier(supplier_id):
    
    return frappe.get_doc("Supplier", supplier_id)

def get_document_types():
    
    list_permited = ["11", "12", "13", "21", "22", "31", "41", "42", "43"]
    
    return frappe.get_all("qp_CO_IdType", filters = {"id_type_id":["in", list_permited]}, fields = ["name", "id_type_name"])

def get_ciius():
    
    return frappe.get_all("qp_CO_CIIU", fields = ["name", "ciiu_name"])

def get_regimes():
    
    return frappe.get_all("qp_CO_TaxRegime", fields = ["name", "tax_regime_name"])

def get_business_types():
    
    return frappe.get_all("qp_CO_BusinessTypes", fields = ["name", "business_type_name"])

def has_recent_news():
    
    from datetime import datetime, timedelta
    
    last_week = datetime.now() - timedelta(days=7)
    
    news = frappe.get_all("qp_SP_Portal_News", filters = {"publish_date": [">=", last_week]}, fields = ["name"], limit=1)
    
    return bool(news)

def get_has_dispatch_permission(supplier_id):

    return frappe.db.exists("Supplier", {"qp_is_transporter": True, "name": supplier_id})