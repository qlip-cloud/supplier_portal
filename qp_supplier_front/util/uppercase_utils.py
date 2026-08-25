# -*- coding: utf-8 -*-
import frappe

def sanitize_colombian_number(val):
    """
    Convierte una cadena en formato de moneda colombiano (ej: 1.250.000,00)
    a formato de float limpio (ej: 1250000.00) legible por base de datos.
    """
    if not isinstance(val, str):
        return val
    if ',' in val:
        # Formato colombiano: Quitar puntos (miles) y reemplazar coma (decimal) por punto
        return val.replace('.', '').replace(',', '.')
    if val.count('.') > 1:
        # Formato de miles pero sin coma decimal explicita (ej: 1.250.000)
        return val.replace('.', '')
    return val

def uppercase_form_inputs():
    """
    Interceptor global de peticiones que convierte a mayúsculas todos los parámetros
    tipo string enviados a los endpoints de qp_supplier_front.resources.information,
    y sanitiza los campos numéricos con formato colombiano.
    """
    cmd = frappe.form_dict.get("cmd") or ""
    if not cmd and frappe.request:
        path = frappe.request.path or ""
        if path.startswith("/api/method/"):
            cmd = path[len("/api/method/"):]
    if cmd and cmd.startswith("qp_supplier_front.resources.information."):
        # Campos numéricos a los que se aplica la máscara de moneda colombiana
        financial_fields = {
            "qp_financial_assets", "qp_financial_liabilities", "qp_financial_equity",
            "qp_financial_other_income", "qp_financial_monthly_income", "qp_financial_monthly_expenses",
            "market_share", "qp_financial_amount"
        }
        
        # Lista de parámetros sensibles o booleanos a omitir de la conversión a mayúsculas
        exclude_keys = {
            "supplier_id", "email", "email_id", "docname", "name", 
            "supplier", "user", "file", "avatar", "password",
            "qp_is_foreigner_supplier", "qp_financial_currency_foreigner", 
            "qp_industry_and_commerce_tax", "qp_self_retaining", 
            "qp_major_contributor", "qp_vat_withholding_agent"
        }
        for key, value in frappe.form_dict.items():
            if isinstance(value, str):
                if key in financial_fields:
                    frappe.form_dict[key] = sanitize_colombian_number(value)
                elif key not in exclude_keys:
                    frappe.form_dict[key] = value.upper()

