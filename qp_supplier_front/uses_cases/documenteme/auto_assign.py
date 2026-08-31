"""
auto_assign.py (documenteme)
============================
Nucleo puro de asignacion automatica de facturas a usuarios.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(DB, configuracion, persistencia) son inyectadas como callbacks.

La asignacion aplica cuando una factura tiene orden de compra y no
tiene recibo de compra asociado, o la sumatoria de las recepciones no
cubre el total de la factura. El destinatario se resuelve segun el tipo de OC:
- Inventariable: el par exacto (oc_type, sede) configurado en
  qp_SP_AssignmentConfig. La orden determina ambas dimensiones.
- No inventariable: solo el oc_type; la sede de la orden no se valida.

Facturas de CONTADO: se asignan (no se aprueban) cuando la regla de rechazo
activa (proveedor o default MasterSetup) exige OC/recibo y la factura no la
cumple. Sin OC se resuelve via una fila catch-all de qp_SP_AssignmentConfig
con oc_type y headquarter vacios. Si la regla no limita (no_action/sin regla)
el contado se aprueba y no se asigna.
"""


from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    RULE_NO_ACTION,
    has_po_match,
    has_receipt_match,
    should_auto_reject,
)
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice


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
    if oc_type is None:
        # Factura de contado sin OC: fila catch-all (headquarter y oc_type
        # vacios) configurada como destinatarios por defecto.
        matching = [
            row for row in (assignment_rows or [])
            if not row.get("oc_type") and not row.get("headquarter")
        ]
        return _dedupe([
            email
            for row in matching
            for email in (row.get("user_emails") or [])
        ])

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
    receipt_total = invoice.get("receipt_total")
    invoice_total = invoice.get("nvfac_stot") or 0
    no_receipt = receipt_total is None
    not_covered = receipt_total != invoice_total
    not_assigned = not invoice.get("assigned_to") and not invoice.get("has_assigned_users")
    in_queue = invoice.get("in_queue", True)
    return (
        in_queue
        and not_assigned
        and has_purchase_order
        and (no_receipt or not_covered)
    )


def should_assign_contado(invoice, resolve_rule_fn, po_exists_fn, receipt_for_po_fn):
    """Una factura de CONTADO se asigna (no se aprueba) si la regla de
    rechazo activa la vulnera (exige OC/recibo y la factura no lo cumplen).

    Con "no_action" o sin regla configurada, el contado se aprueba
    automaticamente y no se asigna.
    """
    if resolve_rule_fn is None:
        return False

    rule = resolve_rule_fn(invoice)
    if not rule:
        return False

    rule_code = rule.get("rule_code")
    if not rule_code or rule_code == RULE_NO_ACTION:
        return False

    po_match = has_po_match(invoice, po_exists_fn)
    receipt_match = has_receipt_match(invoice, receipt_for_po_fn)
    return should_auto_reject(po_match, receipt_match, rule_code)


def auto_assign(
    candidates_fn,
    get_oc_context_fn,
    get_receipt_total_fn,
    resolve_emails_fn,
    resolve_users_fn,
    add_assignees_fn,
    doc_names=None,
    resolve_rule_fn=None,
    po_exists_fn=None,
):
    assigned = []
    candidates = candidates_fn() if doc_names is None else candidates_fn(doc_names)
    for invoice in candidates:
        invoice["receipt_total"] = get_receipt_total_fn(invoice.get("nvfac_orde"))

        cash = is_cash_invoice(invoice.get("nvfac_conv"))
        if cash:
            # Contado: solo se asigna si la regla de rechazo lo bloquea.
            if not should_assign_contado(
                invoice, resolve_rule_fn, po_exists_fn, get_receipt_total_fn
            ):
                continue
        elif not should_auto_assign(invoice):
            continue

        oc_context = get_oc_context_fn(invoice.get("nvfac_orde"))

        if oc_context:
            emails = resolve_emails_fn(
                oc_context.get("oc_type"),
                oc_context.get("headquarter"),
            )
        elif cash:
            # Contado sin OC: destinatarios de la fila catch-all.
            emails = resolve_emails_fn(None, None)
        else:
            continue

        if not emails:
            continue

        users = resolve_users_fn(emails)
        if not users:
            continue

        add_assignees_fn(invoice.get("nvfac_nume"), users)
        assigned.append(invoice.get("nvfac_nume"))

    return assigned
