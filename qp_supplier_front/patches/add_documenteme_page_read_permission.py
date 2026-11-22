import frappe

from qp_supplier_front.patches.add_documenteme_roles import DOCUMENTEME_ROLES


def execute():
    """Permite a los roles de documenteme leer el doctype Page.

    El dialogo de "New Shortcut" del escritorio resuelve el campo link_to
    contra el doctype Page, por lo que sin permiso de lectura el usuario
    no puede seleccionar la pagina "documenteme" al configurar su acceso
    directo (frappe.desk.search.search_widget lanza PermissionError).
    """
    from frappe.permissions import add_permission

    for role_name in DOCUMENTEME_ROLES:
        if not frappe.db.exists("Role", role_name):
            continue
        add_permission("Page", role_name, ptype="read")

    frappe.db.commit()
