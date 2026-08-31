import frappe

from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.repair_primary_contacts import run as run_repair


@frappe.whitelist()
def run(dry_run=1):
    """
    Endpoint GET (solo Administrator) que repara los contactos primarios.
    - dry_run=1: solo reporta los cambios sin escribir en la DB.
    - dry_run=0: aplica los cambios (restaurar/designar primario).
    """
    if "Administrator" not in frappe.get_roles(frappe.session.user):
        response(403, "No tiene permiso para realizar esta accion")
        return

    dry = str(dry_run) not in ("0", "false", "False")

    try:
        report = run_repair(dry_run=dry)
        msg = "Reporte de reparacion de contactos primarios (dry-run)" if dry \
            else "Reparacion de contactos primarios aplicada"
        response(200, msg, report)
    except Exception as error:
        response(500, "Error al reparar contactos: {}".format(str(error)))