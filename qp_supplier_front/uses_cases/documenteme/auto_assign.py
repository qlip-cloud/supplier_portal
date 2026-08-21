"""
auto_assign.py (documenteme)
============================
Nucleo puro de asignacion automatica de facturas a usuarios.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(DB, configuracion, persistencia) son inyectadas como callbacks.

La asignacion aplica cuando una factura tiene orden de compra y recibo
de pago asociado, pero la sumatoria de las recepciones no cubre el total
de la factura. El destinatario se resuelve segun el tipo de OC:
- Inventariable: el par exacto (oc_type, sede) configurado en
  qp_SP_AssignmentConfig. La orden determina ambas dimensiones.
- No inventariable: solo el oc_type; la sede de la orden no se valida.
"""


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


def should_auto_assign(invoice):
    has_purchase_order = bool(invoice.get("nvfac_orde"))
    has_receipt = invoice.get("receipt_total") is not None
    receipt_total = invoice.get("receipt_total") or 0
    invoice_total = invoice.get("nvfac_totp") or 0
    not_covered = receipt_total != invoice_total
    not_assigned = not invoice.get("assigned_to") and not invoice.get("has_assigned_users")
    in_queue = invoice.get("in_queue", True)
    return (
        in_queue
        and not_assigned
        and has_purchase_order
        and has_receipt
        and not_covered
    )


def auto_assign(
    candidates_fn,
    get_oc_context_fn,
    get_receipt_total_fn,
    resolve_emails_fn,
    resolve_users_fn,
    add_assignees_fn,
    doc_names=None,
):
    assigned = []
    candidates = candidates_fn() if doc_names is None else candidates_fn(doc_names)
    for invoice in candidates:
        invoice["receipt_total"] = get_receipt_total_fn(invoice.get("nvfac_orde"))

        if not should_auto_assign(invoice):
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
