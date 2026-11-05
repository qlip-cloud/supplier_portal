"""
add_no_action_reject_rule.py
============================
Patch para crear la regla especial "No hacer nada" (rule_code "no_action")
en qp_SP_AutoRejectRule.

Permite que un proveedor (o el default de qp_SP_MasterSetup) inhiba
explicitamente el rechazo automatico de facturas documenteme, aun cuando el
nivel contrario tenga un default configurado. Es idempotente.
"""

import frappe


DEFAULT_NO_ACTION_RULE = {
    "rule_name": "No hacer nada",
    "rule_code": "no_action",
    "motive": "Sin rechazo automático.",
}


def _ensure_doctype():
    if frappe.db.exists("DocType", "qp_SP_AutoRejectRule"):
        return
    from frappe.modules.import_file import import_file_by_path
    doctype_path = frappe.get_module_path(
        "Qp Supplier Front",
        "doctype",
        "qp_sp_autorejectrule",
        "qp_sp_autorejectrule.json",
    )
    import_file_by_path(doctype_path, force=True, for_sync=True)
    frappe.db.commit()


def execute():
    _ensure_doctype()
    rule = DEFAULT_NO_ACTION_RULE
    if not frappe.db.exists("qp_SP_AutoRejectRule", rule["rule_name"]):
        doc = frappe.get_doc({
            "doctype": "qp_SP_AutoRejectRule",
            "rule_name": rule["rule_name"],
            "rule_code": rule["rule_code"],
            "motive": rule["motive"],
            "enabled": 1,
        })
        doc.insert(ignore_permissions=True)
    frappe.db.commit()