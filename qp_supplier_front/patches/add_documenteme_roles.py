import frappe


DOCUMENTEME_ROLES = [
    "Administrador Documenteme",
    "Administrador Sede Documenteme",
    "Administrador Compras Documenteme",
]


def execute():
    for role_name in DOCUMENTEME_ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.get_doc({"doctype": "Role", "role_name": role_name})
            role.insert()
    frappe.db.commit()