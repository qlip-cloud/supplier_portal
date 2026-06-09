# -*- coding: utf-8 -*-
import frappe

def uppercase_form_inputs():
    """
    Interceptor global de peticiones que convierte a mayúsculas todos los parámetros
    tipo string enviados a los endpoints de qp_supplier_front.resources.information.
    """
    cmd = frappe.form_dict.get("cmd")
    if cmd and cmd.startswith("qp_supplier_front.resources.information."):
        # Lista de parámetros sensibles o booleanos a omitir de la conversión
        exclude_keys = {
            "supplier_id", "email", "email_id", "docname", "name", 
            "supplier", "user", "file", "avatar", "password",
            "qp_is_foreigner_supplier", "qp_financial_currency_foreigner", 
            "qp_industry_and_commerce_tax", "qp_self_retaining", 
            "qp_major_contributor", "qp_vat_withholding_agent"
        }
        for key, value in frappe.form_dict.items():
            if key not in exclude_keys and isinstance(value, str):
                frappe.form_dict[key] = value.upper()
