import frappe
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.uses_cases.information.complete import handler as complete_check


@frappe.whitelist()
def check(supplier_id):

    try:
        supplier = get_supplier(supplier_id)

        complete_check(supplier)

        response(200, "Completado", {"supplier": supplier})

    except Exception as error:
        msg = "Error al verificar finalizacion: {}".format(str(error))
        response(500, msg)
