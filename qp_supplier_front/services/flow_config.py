"""
flow_config.py
===============
Verifica si un flujo de sincronizacion (GP, BC) tiene las credenciales
y configuracion necesarias para operar.

Cada flujo requiere una cadena de Doctypes:
  GP: qp_auth_Endpoint -> qp_auth_Setup -> qp_auth_Enviroment
  BC: qp_md_Endpoint   -> qp_md_Setup   -> qp_md_Enviroment
"""


def is_flow_configured(flow):
    if flow == "GP":
        return _is_gp_configured()
    elif flow == "BC":
        return _is_bc_configured()
    return False


def _is_gp_configured():
    import frappe
    try:
        if not frappe.db.exists("qp_auth_Endpoint", "invoice_supplier_id"):
            return False
        endpoint = frappe.get_doc("qp_auth_Endpoint", "invoice_supplier_id")
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


def _is_bc_configured():
    import frappe
    try:
        if not frappe.db.exists("qp_md_Endpoint", "list_purchase_invoice"):
            return False
        endpoint = frappe.get_doc("qp_md_Endpoint", "list_purchase_invoice")
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
