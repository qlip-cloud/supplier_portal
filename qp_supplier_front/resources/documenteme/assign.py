import frappe
from frappe import parse_json
from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
    RealTimelineAdapter,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.documenteme_access import (
    can_reassign_documenteme,
)
from qp_supplier_front.uses_cases.documenteme.assign import assign_documents
from qp_supplier_front.uses_cases.documenteme.timeline import (
    user_assignment_message,
)


def _forbidden():
    response(403, "No tiene permisos para reasignar facturas")


@frappe.whitelist()
def get_users():
    try:
        if not can_reassign_documenteme(frappe.get_roles()):
            _forbidden()
            return

        users_data = frappe.get_all(
            "User",
            filters={"enabled": 1},
            fields=["name", "first_name", "last_name"]
        )

        response(200, data=users_data, msg="")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener usuarios: {}".format(str(error)))


@frappe.whitelist()
def get_document_data(doc_names):
    try:
        if not can_reassign_documenteme(frappe.get_roles()):
            _forbidden()
            return

        doc_names_list = parse_json(doc_names)

        data = frappe.get_all(
            "qp_SP_DocumentDetail",
            filters={"name": ["in", doc_names_list]},
            fields=["name", "nvfac_nume", "nvfac_orde", "nvfac_rece"]
        )

        response(200, data=data, msg="")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener datos de documentos: {}".format(str(error)))


def _requested_users(users, user):
    """Normaliza la entrada a lista de usuarios.

    Acepta `users` (JSON con varios) y el parametro legacy `user` (uno solo),
    para no romper llamadas existentes al endpoint.
    """
    if not users:
        requested = []
    else:
        try:
            requested = parse_json(users)
        except ValueError:
            requested = users

    if isinstance(requested, str):
        requested = [requested]
    if user:
        requested = list(requested) + [user]

    unique = []
    for value in requested:
        if not value or value in unique:
            continue
        unique.append(value)
    return unique


def _invalid_users(users):
    """Usuarios que no existen o estan deshabilitados."""
    return [
        value for value in users
        if not frappe.db.exists("User", value)
        or not frappe.db.get_value("User", value, "enabled")
    ]


def _assigned_users(sync_line):
    """Usuarios asignados actualmente al sync line (child + legacy)."""
    users = [
        row.get("user")
        for row in frappe.get_all(
            "qp_SP_SyncLineAssignedUser",
            filters={
                "parent": sync_line,
                "parenttype": "qp_SP_DocumentSyncLine",
            },
            fields=["user"],
        )
    ]
    direct = frappe.db.get_value(
        "qp_SP_DocumentSyncLine", sync_line, "assigned_to")
    if direct and direct not in users:
        users.append(direct)
    return users


def _display_names(users):
    """Nombres completos (o email) de los usuarios, sin duplicados."""
    names = []
    for user in (users or []):
        name = frappe.db.get_value("User", user, "full_name") or user
        if name not in names:
            names.append(name)
    return names


@frappe.whitelist()
def assign(doc_names, users=None, user=None):
    try:
        if not can_reassign_documenteme(frappe.get_roles()):
            _forbidden()
            return

        doc_names_list = parse_json(doc_names)
        users_list = _requested_users(users, user)

        if not users_list:
            response(400, "Seleccione al menos un usuario para asignar")
            return

        invalid = _invalid_users(users_list)
        if invalid:
            response(
                400,
                "Usuarios no validos o deshabilitados: {}".format(
                    ", ".join(invalid))
            )
            return

        doc_sync_lines = {}
        for doc_name in doc_names_list:
            sync_line = frappe.db.get_value(
                "qp_SP_DocumentDetail",
                doc_name,
                "document_sync_line"
            )
            if sync_line:
                doc_sync_lines[doc_name] = sync_line

        if not doc_sync_lines:
            response(400, "No se encontraron lineas de sincronizacion para los documentos seleccionados")
            return

        sync_line_names = []
        for sync_line in doc_sync_lines.values():
            if sync_line not in sync_line_names:
                sync_line_names.append(sync_line)

        previous_by_line = {
            sync_line: _assigned_users(sync_line)
            for sync_line in sync_line_names
        }

        assign_documents(
            sync_line_names,
            users_list,
            get_doc_fn=frappe.get_doc,
            save_fn=lambda doc: doc.save(),
        )

        timeline = RealTimelineAdapter(frappe_module=frappe)
        new_names = _display_names(users_list)
        for doc_name, sync_line in doc_sync_lines.items():
            timeline.add_user_assignment(
                doc_name,
                user_assignment_message(
                    new_names,
                    _display_names(previous_by_line.get(sync_line) or []),
                ),
                user=frappe.session.user,
            )

        frappe.db.commit()

        response(200, "Asignacion exitosa")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al asignar: {}".format(str(error)))
