import frappe
from frappe.utils.pdf import get_pdf
from qp_supplier_front.services.get_data import get_supplier, get_party, get_dynamic_link
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import GET_TAX_REPORT_SUPPLIER
from babel.numbers import format_currency,format_decimal
from nlt import numlet as nl
from datetime import datetime
import os
from frappe.utils import get_files_path, now_datetime

REPORT_TYPES = [
    "Retenciones en la fuente",
    "Retenciones IVA",
    "Retenciones ICA"
]
def handler(supplier_id, report_type, fiscal_year, bimester):
    
    supplier = get_supplier(supplier_id)
    
    certificates = get_gp_certificate(supplier, report_type, fiscal_year, bimester)
    
    withholding_id = REPORT_TYPES[int(report_type) - 1]
    
    company = frappe.get_doc("Company", frappe.defaults.get_user_default("company"))
    
    party = get_party(company)
    
    contexts = []
    
    if report_type != "3":
        
        contexts = [get_context(certificates, withholding_id, supplier, party, fiscal_year, bimester, is_location = True)]
        
    else:
        
        contexts = get_context_ica(certificates, withholding_id, supplier, party, fiscal_year, bimester)
    
    return get_pdf(frappe.render_template("templates/pdf/report.html", {"contexts": contexts}))

def get_gp_certificate(supplier, report_type, fiscal_year, bimester):
        
    param = f"{report_type}/{fiscal_year}/{bimester}/{supplier.name}"
    
    result = send_request(GET_TAX_REPORT_SUPPLIER, param = param)
    
    if "status" not in result or result["status"] != 200 or "certificates" not in result:
        
        #error = result["description"] if "description" in result else "Hubo un error obteniendo los datos"
        
        return []
    
    return result["certificates"]

def get_context(certificates, withholding_id, supplier, party, fiscal_year, bimester, city = None, is_location = False):
    
    context = {}
    
    addresses = get_dynamic_link(supplier, "Address")
    
    
    company = {
        "name": certificates[0].get("companyName") if certificates else party.other_name,
        "tax_id":certificates[0].get("nit") if certificates else party.tax_id,
        "address": certificates[0].get("address") if certificates else party.address,
    }
       
    if not city:
        
        city = certificates[0].get("city") if certificates else addresses[0].city
        
        location = "LA DIRECCION DE IMUESTOS Y ADUANAS NACIONALES DIAN"
        
    supplier = {
        "city": city,
        "name": certificates[0].get("vendorName") if certificates else supplier.supplier_name,
        "tax_id":certificates[0].get("vendorId") if certificates else supplier.tax_id
    }
    
    withholdings = []
    
    total_amount = 0
    
    for certificate in certificates:
        
        total_amount += certificate.get("tax")
        
        withholdings.append({
            "description": certificate.get("taxDescription"),
            "base_amount": format_currency(certificate.get("base"), 'COP', u'#,##0.00', locale='es_CO'),
            "porcentage": format_currency(certificate.get("percentageTax"), 'COP', u'#,##0.00', locale='es_CO'),
            "tax_amount": format_currency(certificate.get("tax"), 'COP', u'#,##0.00', locale='es_CO')
        })
    
    dt = datetime.now()    
    ts = datetime.timestamp(dt)
    
    download_control = {
        "withholding_id": withholding_id,
        "name": ts,
        "shipping_date": datetime.now().strftime('%d-%m-%Y %H:%m:%S'),
        "fiscal_year": certificates[0].get("year") if certificates else fiscal_year,
        "period": certificates[0].get("bimester") if certificates else bimester,
        "table_withholding": frappe.render_template("templates/pdf/table_withholding.html", {"withholdings":withholdings}),
        "total_amount": format_currency(total_amount, 'COP', u'#,##0.00', locale='es_CO'),
        "total_str": nl.Numero("{:.2f}".format(total_amount)).a_letras
    }
    
    context = {
        "company": company,
        "supplier": supplier,
        "download_control": download_control,
        "periocity_translate": "Anual" if bimester == "0" else "BIMESTRAL",
        "location": location if is_location else city
    }
    
    return context

def get_context_ica(certificates, withholding_id, supplier, party, fiscal_year, bimester):
    
    contexts = []
    
    cities = {}
    
    if not certificates:
        
        pdf = get_context(certificates, withholding_id, supplier, party, fiscal_year, bimester, is_location = False)
            
        contexts.append(pdf)
        
        return contexts
        
    for certificate in certificates:
        
        city = get_city(certificate.get("taxDescription"))
        
        if city not in cities:
            
            cities.setdefault(city, [])
            
        cities[city].append(certificate)
    
    for city, certificate in cities.items():
        
        pdf = get_context(certificate, withholding_id, supplier, party, fiscal_year, bimester, city)
        
        contexts.append(pdf)

    return contexts
            
def get_city(description):
    
    parts = description.split("RETENCION ICA-")

    return parts[1].split()[0]