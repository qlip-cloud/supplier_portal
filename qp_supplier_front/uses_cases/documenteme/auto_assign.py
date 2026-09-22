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

Facturas de CONTADO: se asignan (no se aprueban) cuando la regla de rechazo
activa (proveedor o default MasterSetup) exige OC/recibo y la factura no la
cumple. Sin OC se resuelve via una fila catch-all de qp_SP_AssignmentConfig
con oc_type y headquarter vacios. Si la regla no limita (no_action/sin regla)
el contado se aprueba y no se asigna.
"""

from qp_supplier_front.uses_cases.documenteme.receipt_bank import (
    DEFAULT_EPSILON,
    solve_receipt_bank,
)


from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    RULE_NO_ACTION,
    has_po_match,
    has_receipt_match,
    should_auto_reject,
)
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice

NO_APLICA = "No aplica"


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


def _is_wildcard(row):
    """Fila "No aplica": se asigna sin importar OC type ni headquarter."""
    return row.get("oc_type") == NO_APLICA


def _is_catch_all(row):
    """Fila catch-all: oc_type vacio (o "No aplica") y sin headquarter."""
    return (not row.get("oc_type") or row.get("oc_type") == NO_APLICA) \
        and not row.get("headquarter")


def resolve_assignee_emails(
        oc_type, headquarter, oc_type_rows, assignment_rows,
        roles_to_users_fn=None):
    """Resuelve los emails destino para una factura.

    Las filas "No aplica" (oc_type = NO_APLICA) son wildcard: se asigna sin
    importar el OC type ni la sede, tanto para contado sin OC como para
    cualquier factura con OC. Se suman a las filas con match exacto.

    roles_to_users_fn: callback opcional que recibe la lista de roles de las
    filas que hicieron match y devuelve los emails de los usuarios con esos
    roles (complemento de user_emails; _dedupe evita duplicados).
    """
    rows = assignment_rows or []
    wildcards = [row for row in rows if _is_wildcard(row)]

    if oc_type is None:
        # Factura de contado sin OC: fila catch-all (oc_type y headquarter
        # vacios) o fila wildcard "No aplica".
        matching = [
            row for row in rows if _is_catch_all(row)
        ] + wildcards
    else:
        inventariable = is_inventariable_oc_type(oc_type, oc_type_rows)

        if inventariable is None:
            if not wildcards:
                return None
            matching = wildcards
        else:
            matcher = _MATCHERS[inventariable]
            matching = [
                row for row in rows
                if matcher(row, oc_type, headquarter)
            ] + wildcards

    emails = [
        email
        for row in matching
        for email in (row.get("user_emails") or [])
    ]

    roles = _dedupe([
        role
        for row in matching
        for role in (row.get("user_roles") or [])
    ])
    if roles and roles_to_users_fn is not None:
        emails += (roles_to_users_fn(roles) or [])

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
        invoice.get("nvfac_stot") or 0, receipt_bank or [], epsilon
    ) is None


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


def _service_supplier(invoice, is_service_supplier_fn):
    return (
        is_service_supplier_fn is not None
        and bool(is_service_supplier_fn(invoice))
    )


def auto_assign(
    candidates_fn,
    get_oc_context_fn,
    get_receipt_bank_fn,
    resolve_emails_fn,
    resolve_users_fn,
    add_assignees_fn,
    doc_names=None,
    resolve_rule_fn=None,
    po_exists_fn=None,
    is_service_supplier_fn=None,
    epsilon=DEFAULT_EPSILON,
):
    assigned = []
    candidates = candidates_fn() if doc_names is None else candidates_fn(doc_names)
    for invoice in candidates:
        # Proveedor de servicio (flujo GP): la OC y las recepciones NO son
        # obligatorias. La factura se auto-aprueba (si su regla de rechazo lo
        # permite) o se auto-rechaza; nunca se asigna por falta de recibos.
        if _service_supplier(invoice, is_service_supplier_fn):
            continue

        bank = get_receipt_bank_fn(invoice.get("nvfac_orde"))

        cash = is_cash_invoice(invoice.get("nvfac_conv"))
        if cash:
            # Contado: solo se asigna si la regla de rechazo lo bloquea.
            if not should_assign_contado(
                invoice,
                resolve_rule_fn,
                po_exists_fn,
                lambda po: get_receipt_bank_fn(po) or None,
            ):
                continue
        elif not should_auto_assign(invoice, bank, epsilon):
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
