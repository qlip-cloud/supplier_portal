import frappe

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_receipt_bank as _adapter_get_receipt_bank,
    get_receipt_total as _adapter_get_receipt_total,
)
from qp_supplier_front.resources.documenteme.auto_reject import (
    po_exists as _po_exists,
    resolve_rule as _resolve_rule,
)
from qp_supplier_front.resources.documenteme._approve_base import (
    is_service_supplier_doc as _is_service_supplier_doc,
    po_supplier_match,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.qp_supplier_front.doctype.qp_sp_assignmentconfig.qp_sp_assignmentconfig import (
    _normalize_headquarter,
    _normalize_oc_type,
)
from qp_supplier_front.services.sede_source import sede_exists
from qp_supplier_front.uses_cases.documenteme.auto_assign import (
    auto_assign as auto_assign_core,
    is_inventariable_oc_type,
    resolve_assignee_emails,
)
from qp_supplier_front.uses_cases.documenteme.no_purchase_order import (
    INVOICE_TYPE_CREDIT,
)
from qp_supplier_front.uses_cases.documenteme.purchase_orders import (
    parse_purchase_orders,
)


def run_auto_assign(doc_names=None):
    from qp_supplier_front.infrastructure.adapters.master_setup_source import (
        RealMasterSetupSource,
    )

    assign_without_po = RealMasterSetupSource(
        frappe_module=frappe).assign_without_po_enabled()

    return auto_assign_core(
        candidates_fn=get_candidates,
        get_oc_context_fn=get_oc_context,
        get_receipt_bank_fn=get_receipt_bank,
        resolve_emails_fn=get_assignee_emails,
        resolve_users_fn=resolve_assignee_users,
        add_assignees_fn=add_assignees,
        doc_names=doc_names,
        resolve_rule_fn=_resolve_rule,
        po_exists_fn=_po_exists,
        is_service_supplier_fn=_is_service_supplier_doc,
        po_supplier_match_fn=po_supplier_match,
        assign_without_po=assign_without_po,
        mark_pending_oc_fn=mark_pending_oc,
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
    from qp_supplier_front.infrastructure.adapters.receipt_claim_adapter import (
        claimed_invoice_numbers,
    )
    from qp_supplier_front.uses_cases.documenteme.notification_state import (
        is_pending_ueve,
    )

    filters = {
        "nvfac_esta": ["not in", ["PSA", "BCC", "PA", "PR", "A", "R", "SR"]],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    docs = frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
        fields=["name", "nvfac_nume", "nvpro_ndoc", "nvfac_orde", "nvfac_totp", "nvfac_stot", "nvfac_esta", "nvfac_ueve", "nvfac_conv", "nvtip_docu", "document_sync_line"],
    )

    # Seleccion manual en curso (recibos reclamados): se excluye del flujo
    # automatico (manual excluye auto).
    claimed = claimed_invoice_numbers()

    candidates = []
    for doc in docs:
        if not is_pending_ueve(doc.get("nvfac_ueve")):
            continue
        if doc.get("nvfac_nume") in claimed:
            continue
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
            "nvpro_ndoc": doc.get("nvpro_ndoc"),
            "nvfac_orde": doc.get("nvfac_orde"),
            "nvfac_totp": doc.get("nvfac_totp"),
            "nvfac_stot": doc.get("nvfac_stot"),
            "nvfac_conv": doc.get("nvfac_conv"),
            "nvtip_docu": doc.get("nvtip_docu"),
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


def get_receipt_bank(purchase_order_number):
    """Banco de recepciones (name, amount, date, qp_invoice) por OC."""
    return _adapter_get_receipt_bank(
        purchase_order_number, frappe_module=frappe
    )


def get_receipt_total(purchase_order_number):
    """Suma del total de Purchase Receipt por OC (delega en el adapter)."""
    return _adapter_get_receipt_total(
        purchase_order_number, frappe_module=frappe
    )


def get_assignee_emails(oc_type, headquarter, has_receipt=None,
                        invoice_type=None):
    oc_type_records = frappe.get_all(
        "qp_SP_OCType", fields=["name", "oc_type", "is_inventariable"]
    )
    oc_type_rows = [
        {"oc_type": row.get("name"), "is_inventariable": row.get("is_inventariable")}
        for row in (oc_type_records or [])
        if row.get("name")
    ]

    if is_inventariable_oc_type(oc_type, oc_type_rows) and headquarter and not sede_exists(headquarter):
        return None

    assignment_rows = _load_assignment_rows(oc_type_records)
    return resolve_assignee_emails(
        oc_type,
        headquarter,
        oc_type_rows,
        assignment_rows,
        roles_to_users_fn=resolve_role_users,
        has_receipt=has_receipt,
        invoice_type=invoice_type,
    )


def resolve_role_users(roles):
    """Emails de usuarios habilitados que tengan alguno de los roles."""
    emails = []
    for role in (roles or []):
        if not role:
            continue
        parents = frappe.get_all(
            "Has Role",
            filters={"role": role, "parenttype": "User"},
            pluck="parent",
        )
        if not parents:
            continue
        enabled = frappe.get_all(
            "User",
            filters={"name": ["in", list(parents)], "enabled": 1},
            pluck="name",
        )
        for email in (enabled or []):
            if email and email not in emails:
                emails.append(email)
    return emails


def _load_assignment_rows(oc_type_records=None):
    if oc_type_records is None:
        oc_type_records = frappe.get_all(
            "qp_SP_OCType", fields=["name", "oc_type"]
        )

    configs = frappe.get_all(
        "qp_SP_AssignmentConfig",
        fields=["name", "headquarter", "oc_type", "invoice_type"],
    )

    rows = []
    for config in configs:
        child_rows = frappe.get_all(
            "qp_SP_AssignmentConfigUser",
            filters={"parent": config["name"], "parenttype": "qp_SP_AssignmentConfig"},
            fields=["user_email", "receipt_preference"],
        )
        role_rows = frappe.get_all(
            "qp_SP_AssignmentConfigRole",
            filters={"parent": config["name"], "parenttype": "qp_SP_AssignmentConfig"},
            fields=["role"],
        )
        rows.append({
            "headquarter": _normalize_headquarter(config.get("headquarter")),
            "oc_type": _normalize_oc_type(config.get("oc_type"), oc_type_records),
            "invoice_type": config.get("invoice_type"),
            "user_emails": [row.get("user_email") for row in child_rows],
            "user_preferences": {
                row.get("user_email"): row.get("receipt_preference")
                for row in child_rows
            },
            "user_roles": [row.get("role") for row in role_rows],
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


def mark_pending_oc(detail_name):
    """Marca la factura en "SO" (Sin OC) y lo registra en el timeline."""
    if not detail_name:
        return
    if not frappe.db.exists("qp_SP_DocumentDetail", detail_name):
        return

    frappe.db.set_value(
        "qp_SP_DocumentDetail", detail_name, "nvfac_esta", "SO")

    from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
        RealTimelineAdapter,
    )
    RealTimelineAdapter(frappe_module=frappe).set_state(detail_name, "SO")


def _unique(items):
    unique = []
    for item in (items or []):
        if item and item not in unique:
            unique.append(item)
    return unique


def reassign_to_oc_group(detail_name):
    """Prepara la reasignacion de la factura al grupo de su OC.

    Resuelve el grupo `(oc_type, headquarter)` de las OC de la factura. Si no
    resuelve destinatarios, conserva la asignacion actual (nunca deja la
    factura huerfana). Si resuelve, limpia `assigned_to` y `assigned_users`
    del sync line para que el pipeline normal decida: si el banco cubre el
    total no queda asignada (pasa a V) y si no, se asigna al grupo de la OC.

    Retorna un dict con `reassigned`, `previous`, `users`, `emails` y `reason`.
    """
    if not detail_name:
        return {"reassigned": False, "reason": "sin_documento"}

    doc = frappe.get_doc("qp_SP_DocumentDetail", detail_name)
    sync_line = doc.get("document_sync_line")
    if not sync_line:
        return {"reassigned": False, "reason": "sin_sync_line"}

    orders = parse_purchase_orders(doc.get("nvfac_orde"))
    emails = []
    valid_context = False
    for order in orders:
        oc_context = get_oc_context(order)
        if not oc_context:
            continue
        valid_context = True
        bank = get_receipt_bank(order)
        emails += get_assignee_emails(
            oc_context.get("oc_type"),
            oc_context.get("headquarter"),
            has_receipt=bool(bank),
            invoice_type=INVOICE_TYPE_CREDIT,
        ) or []

    if not valid_context:
        return {"reassigned": False, "reason": "sin_oc_valida"}

    users = resolve_assignee_users(_unique(emails))
    if not users:
        return {
            "reassigned": False,
            "reason": "sin_grupo",
            "emails": _unique(emails),
        }

    line = frappe.get_doc("qp_SP_DocumentSyncLine", sync_line)
    previous = [row.user for row in line.assigned_users]
    if line.assigned_to:
        previous.append(line.assigned_to)

    line.assigned_to = None
    line.set("assigned_users", [])
    line.save()

    return {
        "reassigned": True,
        "previous": _unique(previous),
        "users": users,
        "emails": _unique(emails),
    }
