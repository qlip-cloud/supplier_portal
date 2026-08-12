import frappe


DEFAULT_AUTO_REJECT_RULES = [
    {
        "rule_name": "Sin coincidencia con Orden de Compra",
        "rule_code": "no_po",
        "motive": "Rechazo automático: la factura no coincide con ninguna orden de compra.",
    },
    {
        "rule_name": "Sin coincidencia con Recibo de Compra",
        "rule_code": "no_receipt",
        "motive": "Rechazo automático: la factura no coincide con ningún recibo de compra.",
    },
    {
        "rule_name": "Sin coincidencia con Orden de Compra ni Recibo",
        "rule_code": "no_po_no_receipt",
        "motive": "Rechazo automático: la factura no coincide con ninguna orden de compra ni recibo de compra.",
    },
]


def execute():
    for rule in DEFAULT_AUTO_REJECT_RULES:
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
