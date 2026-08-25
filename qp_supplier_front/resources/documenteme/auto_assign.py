import frappe

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_receipt_total as _adapter_get_receipt_total,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.sede_source import sede_exists
from qp_supplier_front.uses_cases.documenteme.auto_assign import (
    auto_assign as auto_assign_core,
    is_inventariable_oc_type,
    resolve_assignee_emails,
)


def run_auto_assign(doc_names=None):
    return auto_assign_core(
        candidates_fn=get_candidates,
        get_oc_context_fn=get_oc_context,
        get_receipt_total_fn=get_receipt_total,
        resolve_emails_fn=get_assignee_emails,
        resolve_users_fn=resolve_assignee_users,
        add_assignees_fn=add_assignees,
        doc_names=doc_names,
    )


@frappe.whitelist()
def auto_assign():
    try:
        assigned = run_auto_assign()
        frappe.db.commit()
        response(200, "Asignacion automatica exitosa", {"assigned": assigned})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error en asignacion automatica: {}".format(str(error)))


def get_candidates(doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": ["not in", ["BCC", "PA", "PR"]],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    docs = frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
        fields=["name", "nvfac_nume", "nvfac_orde", "nvfac_totp", "nvfac_esta", "document_sync_line"],
    )

    candidates = []
    for doc in docs:
        sync_line = doc.get("document_sync_line") or doc.get("nvfac_nume")
        if not sync_line or not frappe.db.exists("qp_SP_DocumentSyncLine", sync_line):
            continue

        assigned_to = frappe.db.get_value("qp_SP_DocumentSyncLine", sync_line, "assigned_to")
        has_assigned_users = bool(frappe.db.exists("qp_SP_SyncLineAssignedUser", {
            "parent": sync_line,
            "parenttype": "qp_SP_DocumentSyncLine",
        }))

        candidates.append({
            "name": doc.get("name"),
            "nvfac_nume": sync_line,
            "nvfac_orde": doc.get("nvfac_orde"),
            "nvfac_totp": doc.get("nvfac_totp"),
            "assigned_to": assigned_to,
            "has_assigned_users": has_assigned_users,
            "in_queue": True,
        })

    return candidates


def get_oc_context(purchase_order_number):
    if not purchase_order_number:
        return None

    if not frappe.db.exists("Purchase Order", purchase_order_number):
        return None

    values = frappe.db.get_value(
        "Purchase Order",
        purchase_order_number,
        ["qp_oc_type", "qp_headquarter", "qp_order_confirmation_no"],
    )
    if values is None:
        return None

    if values[2] != purchase_order_number:
        return None

    return {"oc_type": values[0], "headquarter": values[1]}


def get_receipt_total(purchase_order_number):
    """Suma del total de Purchase Receipt por OC (delega en el adapter)."""
    return _adapter_get_receipt_total(
        purchase_order_number, frappe_module=frappe
    )


def get_assignee_emails(oc_type, headquarter):
    oc_type_rows = frappe.get_all("qp_SP_OCType", fields=["oc_type", "is_inventariable"])

    if is_inventariable_oc_type(oc_type, oc_type_rows) and headquarter and not sede_exists(headquarter):
        return None

    assignment_rows = _load_assignment_rows()
    return resolve_assignee_emails(oc_type, headquarter, oc_type_rows, assignment_rows)


def _load_assignment_rows():
    configs = frappe.get_all(
        "qp_SP_AssignmentConfig",
        fields=["name", "headquarter", "oc_type"],
    )

    rows = []
    for config in configs:
        child_rows = frappe.get_all(
            "qp_SP_AssignmentConfigUser",
            filters={"parent": config["name"], "parenttype": "qp_SP_AssignmentConfig"},
            fields=["user_email"],
        )
        rows.append({
            "headquarter": config.get("headquarter"),
            "oc_type": config.get("oc_type"),
            "user_emails": [row.get("user_email") for row in child_rows],
        })

    return rows


def resolve_assignee_users(emails):
    users = []
    for email in (emails or []):
        if not email:
            continue
        if frappe.db.exists("User", email) and frappe.db.get_value("User", email, "enabled"):
            if email not in users:
                users.append(email)
    return users


def add_assignees(sync_line_name, users):
    line = frappe.get_doc("qp_SP_DocumentSyncLine", sync_line_name)
    existing = {row.user for row in line.assigned_users}

    for user in (users or []):
        if user in existing:
            continue
        line.append("assigned_users", {"user": user})

    line.save()
