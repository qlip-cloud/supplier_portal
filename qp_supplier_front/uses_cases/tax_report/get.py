import frappe
from frappe.utils.pdf import get_pdf
from qp_supplier_front.services.get_data import get_supplier
from qp_authorization.use_case.bearer.authorize import send_request
from qp_supplier_front.constant.endpoint import GET_TAX_REPORT_SUPPLIER
from babel.numbers import format_currency,format_decimal
from nlt import numlet as nl
from datetime import datetime

REPORT_TYPES = [
    "Retenciones en la fuente",
    "Retenciones IVA",
    "Retenciones ICA"
]
def handler(supplier_id, report_type, fiscal_year, bimester):
    
    supplier = get_supplier(supplier_id)
    
    certificates = get_gp_certificate(supplier, report_type, fiscal_year, bimester)
    
    withholding_id = REPORT_TYPES[int(report_type) - 1]
    
    pdf = generate_pdf(certificates, withholding_id)

    return pdf

def get_gp_certificate(supplier, report_type, fiscal_year, bimester):
    
    param = f"{report_type}/{fiscal_year}/{bimester}/805011877"
    
    #param = f"/{report_type}/{fiscal_year}/{bimester}/{supplier.gp_vendor_id or "805011877"}"
    
    result = send_request(GET_TAX_REPORT_SUPPLIER, param = param)
    
    
    if "status" not in result or result["status"] != 200 or "certificates" not in result:
        
        error = result["description"] if "description" in result else "Hubo un error obteniendo los datos"
        
        return []
    
    return result["certificates"]

def generate_pdf(certificates, withholding_id):
    context = {}
    if certificates:
        
        company = {
            "name": certificates[0].get("companyName"),
            "tax_id":certificates[0].get("nit"),
            "address": certificates[0].get("address")
        }
        
        supplier = {
            "city": certificates[0].get("city"),
            "name": certificates[0].get("vendorName"),
            "tax_id":certificates[0].get("vendorId")
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
            "fiscal_year": certificates[0].get("year"),
            "period": certificates[0].get("bimester"),
            "table_withholding": frappe.render_template("templates/pdf/table_withholding.html", {"withholdings":withholdings}),
            "total_amount": format_currency(total_amount, 'COP', u'#,##0.00', locale='es_CO'),
            "total_str": nl.Numero("{:.2f}".format(total_amount)).a_letras
        }
        
        context = {
            "company": company,
            "supplier": supplier,
            "download_control": download_control,
            "periocity_translate": "Anual" if certificates[0].get("bimester") == 0 else "BIMESTRAL"
        }
    
    return get_pdf(frappe.render_template("templates/pdf/report.html", context))