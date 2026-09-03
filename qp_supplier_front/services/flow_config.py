"""
flow_config.py
===============
Verifica si un flujo de sincronizacion (GP, BC) para un dominio
especifico tiene las credenciales y configuracion necesarias.

Cada flujo requiere una cadena de Doctypes:
  GP: qp_auth_Endpoint -> qp_auth_Setup -> qp_auth_Enviroment
  BC: qp_md_Endpoint   -> qp_md_Setup   -> qp_md_Enviroment
"""


ENDPOINT_CODES = {
    ("GP", "invoice"): "invoice_supplier_id",
    ("GP", "receipt"): "payment_supplier_id",
    ("GP", "supplier"): "supplier_find",
    ("BC", "invoice"): "list_purchase_invoice",
    ("BC", "receipt"): "list_payment_receipt",
    ("BC", "supplier"): "supplier_find",
}


def is_flow_configured(flow, domain="invoice"):
    endpoint_code = ENDPOINT_CODES.get((flow, domain))
    if not endpoint_code:
        return False
    if flow == "GP":
        return _check_gp(endpoint_code)
    elif flow == "BC":
        return _check_bc(endpoint_code)
    return False


def _check_gp(endpoint_code):
    import frappe
    try:
        if not frappe.db.exists("qp_auth_Endpoint", endpoint_code):
            return False
        endpoint = frappe.get_doc("qp_auth_Endpoint", endpoint_code)
        if not endpoint.setup:
            return False
        if not frappe.db.exists("qp_auth_Setup", endpoint.setup):
            return False
        setup = frappe.get_doc("qp_auth_Setup", endpoint.setup)
        if not setup.enviroment:
            return False
        if not frappe.db.exists("qp_auth_Enviroment", setup.enviroment):
            return False
        env = frappe.get_doc("qp_auth_Enviroment", setup.enviroment)
        if not env.url or not env.user or not env.password:
            return False
        return True
    except Exception:
        return False


def _check_bc(endpoint_code):
    import frappe
    try:
        if not frappe.db.exists("qp_md_Endpoint", endpoint_code):
            return False
        endpoint = frappe.get_doc("qp_md_Endpoint", endpoint_code)
        if not endpoint.setup:
            return False
        if not frappe.db.exists("qp_md_Setup", endpoint.setup):
            return False
        setup = frappe.get_doc("qp_md_Setup", endpoint.setup)
        if not setup.enviroment:
            return False
        if not frappe.db.exists("qp_md_Enviroment", setup.enviroment):
            return False
        env = frappe.get_doc("qp_md_Enviroment", setup.enviroment)
        if not env.url:
            return False
        return True
    except Exception:
        return False
