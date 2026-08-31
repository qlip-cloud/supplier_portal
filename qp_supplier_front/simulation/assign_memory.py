# -*- coding: utf-8 -*-
"""
assign_memory.py (documenteme simulation)
=========================================
Asignacion automatica en memoria: enlaza el nucleo puro de auto-asignacion
(uses_cases/documenteme/auto_assign.py) al MemoryStore de la sesion, replicando
la infraestructura real (resources/documenteme/auto_assign.py) sin Frappe.

En el modo simulador, run_documenteme_auto_assign (sync_all_whitelist) invoca
este modulo en lugar de la implementacion Frappe cuando el facade de datos es
in-memory, para que las facturas sin combinacion exacta de recepciones queden
asignadas a los usuarios configurados (qp_SP_AssignmentConfig).
"""

from qp_supplier_front.uses_cases.documenteme.auto_assign import (
    auto_assign as auto_assign_core,
    is_inventariable_oc_type,
    resolve_assignee_emails,
)


def _sync_line(store, doc):
    line = doc.get("document_sync_line") or doc.get("nvfac_nume")
    if not line or not store.exists("qp_SP_DocumentSyncLine", line):
        return None
    return line


def _has_assigned_users(store, sync_line):
    return store.count(
        "qp_SP_SyncLineAssignedUser",
        filters={"parent": sync_line},
    ) > 0


def _candidates(store, doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": ["not in", ["BCC", "PA", "PR", "A", "R"]],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    docs = store.query(
        "qp_SP_DocumentDetail",
        filters=filters,
        fields=["name", "nvfac_nume", "nvfac_orde", "nvfac_totp", "nvfac_stot",
                "nvfac_esta", "nvfac_conv", "document_sync_line"],
    )

    candidates = []
    for doc in docs:
        sync_line = _sync_line(store, doc)
        if sync_line is None:
            continue
        assigned_to = store.get_value(
            "qp_SP_DocumentSyncLine", sync_line, "assigned_to")
        candidates.append({
            "name": doc.get("name"),
            "nvfac_nume": sync_line,
            "nvfac_orde": doc.get("nvfac_orde"),
            "nvfac_totp": doc.get("nvfac_totp"),
            "nvfac_stot": doc.get("nvfac_stot"),
            "nvfac_conv": doc.get("nvfac_conv"),
            "assigned_to": assigned_to,
            "has_assigned_users": _has_assigned_users(store, sync_line),
            "in_queue": True,
        })

    return candidates


def _oc_context(store, purchase_order_number):
    if not purchase_order_number:
        return None
    row = store.get("qp_SP_PurchaseOrder", purchase_order_number)
    if not row:
        return None
    if row.get("qp_order_confirmation_no") != purchase_order_number:
        return None
    return {
        "oc_type": row.get("qp_oc_type"),
        "headquarter": row.get("qp_headquarter"),
    }


def _normalize_headquarter(value):
    if not value:
        return ""
    return str(value).split("\n", 1)[0].strip()


def _normalize_oc_type(value, oc_type_rows):
    value = (value or "").strip()
    if not value:
        return ""
    for row in (oc_type_rows or []):
        if value == row.get("name") or value == row.get("oc_type"):
            return row.get("name")
    return value


def _load_assignment_rows(store, oc_type_records=None):
    if oc_type_records is None:
        oc_type_records = store.query(
            "qp_SP_OCType", fields=["name", "oc_type"])
    configs = store.query(
        "qp_SP_AssignmentConfig",
        fields=["name", "headquarter", "oc_type"],
    )
    rows = []
    for config in (configs or []):
        child_rows = store.query(
            "qp_SP_AssignmentConfigUser",
            filters={"parent": config["name"],
                     "parenttype": "qp_SP_AssignmentConfig"},
            fields=["user_email"],
        )
        rows.append({
            "headquarter": _normalize_headquarter(config.get("headquarter")),
            "oc_type": _normalize_oc_type(config.get("oc_type"), oc_type_records),
            "user_emails": [row.get("user_email") for row in child_rows],
        })
    return rows


def _assignee_emails(store, oc_type, headquarter):
    oc_type_records = store.query(
        "qp_SP_OCType", fields=["name", "oc_type", "is_inventariable"])
    oc_type_rows = [
        {"oc_type": row.get("name"),
         "is_inventariable": row.get("is_inventariable")}
        for row in (oc_type_records or [])
        if row.get("name")
    ]

    if (is_inventariable_oc_type(oc_type, oc_type_rows)
            and headquarter
            and not store.exists("qp_md_headquarter", headquarter)):
        return None

    assignment_rows = _load_assignment_rows(store, oc_type_records)
    return resolve_assignee_emails(
        oc_type, headquarter, oc_type_rows, assignment_rows)


def _assignee_users(store, emails):
    users = []
    for email in (emails or []):
        if not email:
            continue
        if store.exists("User", email) and store.get_value(
                "User", email, "enabled"):
            if email not in users:
                users.append(email)
    return users


def _add_assignees(store, sync_line_name, users):
    existing = set(store.query(
        "qp_SP_SyncLineAssignedUser",
        filters={"parent": sync_line_name},
        pluck="user",
    ))
    for user in (users or []):
        if user in existing:
            continue
        store.insert("qp_SP_SyncLineAssignedUser", {
            "parent": sync_line_name,
            "parenttype": "qp_SP_DocumentSyncLine",
            "user": user,
        })


def run_auto_assign(store, doc_names=None):
    """Asignacion automatica del escenario sobre el store de la sesion.

    No hay regla de rechazo activa (None), por lo que los contados no se
    asignan; se asignan las facturas de credito con OC sin combinacion
    exacta de recepciones.
    """
    return auto_assign_core(
        candidates_fn=lambda names=None: _candidates(store, names),
        get_oc_context_fn=lambda po: _oc_context(store, po),
        get_receipt_bank_fn=lambda po: _receipt_bank(store, po),
        resolve_emails_fn=lambda oc_type, hq: _assignee_emails(
            store, oc_type, hq),
        resolve_users_fn=lambda emails: _assignee_users(store, emails),
        add_assignees_fn=lambda line, users: _add_assignees(
            store, line, users),
        doc_names=doc_names,
        resolve_rule_fn=None,
        po_exists_fn=lambda po: _po_exists(store, po),
    )


def _po_exists(store, purchase_order):
    if not purchase_order:
        return False
    return store.exists("qp_SP_PurchaseOrder", purchase_order)


def _receipt_bank(store, purchase_order):
    from qp_supplier_front.simulation import references_memory
    return references_memory.memory_get_receipt_bank(store, purchase_order)