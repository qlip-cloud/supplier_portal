import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.www.information.index import get_is_alpla_admin
from qp_supplier_front.uses_cases.supplier.sync_supplier import sync_supplier_to_flows

APPROVE = "Aprobado"


def handler(supplier_id):

    assert_that_user_has_permission()

    supplier = get_supplier(supplier_id)

    assert_that_supplier_is_pre_approved(supplier)

    supplier.qp_status = APPROVE

    sync_supplier_to_flows(supplier)

    supplier.save()

    from qp_supplier_front.services.snapshot import clear_snapshot
    clear_snapshot(supplier_id)

    return {
        "supplier": supplier
    }


def assert_that_supplier_is_pre_approved(supplier):

    if not supplier.qp_preapproved:

        frappe.throw("El proveedor debe ser pre aprobado, para poder realizar esta accion")


def assert_that_user_has_permission():

    user = frappe.session.user

    user_roles = frappe.get_roles(user)

    if not get_is_alpla_admin(user_roles, "Alpla Finanzas"):

        frappe.throw("No tiene permiso para realizar esta funcion")
