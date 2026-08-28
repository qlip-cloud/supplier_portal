"""
auto_assign.py (documenteme)
============================
Nucleo puro de asignacion automatica de facturas a usuarios.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(DB, configuracion, persistencia) son inyectadas como callbacks.

La asignacion aplica cuando una factura tiene orden de compra y no
esta cubierta por una combinacion exacta de recepciones no consumidas
(banco de recepciones). El destinatario se resuelve segun el tipo de OC:
- Inventariable: el par exacto (oc_type, sede) configurado en
  qp_SP_AssignmentConfig. La orden determina ambas dimensiones.
- No inventariable: solo el oc_type; la sede de la orden no se valida.
"""

from qp_supplier_front.uses_cases.documenteme.receipt_bank import (
    DEFAULT_EPSILON,
    solve_receipt_bank,
)


def is_inventariable_oc_type(oc_type, oc_type_rows):
    for row in (oc_type_rows or []):
        if row.get("oc_type") == oc_type:
            return bool(row.get("is_inventariable"))
    return None


def _match_inventariable(row, oc_type, headquarter):
    return row.get("oc_type") == oc_type and row.get("headquarter") == headquarter


def _match_no_inventariable(row, oc_type, headquarter):
    return row.get("oc_type") == oc_type


_MATCHERS = {
    True: _match_inventariable,
    False: _match_no_inventariable,
}


def resolve_assignee_emails(oc_type, headquarter, oc_type_rows, assignment_rows):
    inventariable = is_inventariable_oc_type(oc_type, oc_type_rows)

    if inventariable is None:
        return None

    matcher = _MATCHERS[inventariable]
    matching = [
        row for row in (assignment_rows or [])
        if matcher(row, oc_type, headquarter)
    ]

    emails = [
        email
        for row in matching
        for email in (row.get("user_emails") or [])
    ]

    return _dedupe(emails)


def _dedupe(items):
    unique = []
    for item in (items or []):
        if item and item not in unique:
            unique.append(item)
    return unique


def should_auto_assign(invoice, receipt_bank=None, epsilon=DEFAULT_EPSILON):
    """True si la factura debe asignarse automaticamente.

    Una factura con orden de compra se asigna cuando no esta cubierta por
    una combinacion exacta de recepciones no consumidas. Si las recepciones
    de su OC ya fueron consumidas por otra factura aprobada, el banco no
    tendra combinacion exacta y la factura quedara para asignacion.
    """
    has_purchase_order = bool(invoice.get("nvfac_orde"))
    not_assigned = not invoice.get("assigned_to") and not invoice.get("has_assigned_users")
    in_queue = invoice.get("in_queue", True)
    if not (in_queue and not_assigned and has_purchase_order):
        return False
    return solve_receipt_bank(
        invoice.get("nvfac_totp") or 0, receipt_bank or [], epsilon
    ) is None


def auto_assign(
    candidates_fn,
    get_oc_context_fn,
    get_receipt_bank_fn,
    resolve_emails_fn,
    resolve_users_fn,
    add_assignees_fn,
    doc_names=None,
    epsilon=DEFAULT_EPSILON,
):
    assigned = []
    candidates = candidates_fn() if doc_names is None else candidates_fn(doc_names)
    for invoice in candidates:
        bank = get_receipt_bank_fn(invoice.get("nvfac_orde"))

        if not should_auto_assign(invoice, bank, epsilon):
            continue

        oc_context = get_oc_context_fn(invoice.get("nvfac_orde"))
        if not oc_context:
            continue

        emails = resolve_emails_fn(
            oc_context.get("oc_type"),
            oc_context.get("headquarter"),
        )
        if not emails:
            continue

        users = resolve_users_fn(emails)
        if not users:
            continue

        add_assignees_fn(invoice.get("nvfac_nume"), users)
        assigned.append(invoice.get("nvfac_nume"))

    return assigned
