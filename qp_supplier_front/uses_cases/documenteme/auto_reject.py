"""
auto_reject.py (documenteme)
============================
Nucleo puro del rechazo automatico de facturas documenteme.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(DB, configuracion, persistencia, notificacion) son inyectadas como callbacks.

El comportamiento replica exactamente el rechazo manual de documenteme
(uses_cases/documenteme/reject.py) sin requerir interaccion del usuario:
- Solo se consideran facturas en estado "E" (guard igual al manual).
- La secuencia de eventos 030 -> 032 -> 031 la ejecuta el job de fondo.
- La factura se marca "R" solo cuando la secuencia completa tiene exito;
  si falla, permanece en "E" y se reintenta en el siguiente ciclo.

Una factura se rechaza cuando no coincide con los documentos de compra
segun la regla configurada (por proveedor o por defecto global):
- no_po:            rechazar si no coincide con ninguna orden de compra.
- no_receipt:       rechazar si no coincide con ningun recibo de compra.
- no_po_no_receipt: rechazar si no coincide con orden de compra ni recibo.

El campo vacio / regla no habilitada equivale a "No configurado".

La regla especial "no_action" ("No hacer nada") permite que un proveedor
inhiba explicitamente el rechazo automatico aunque el setup global tenga un
default configurado. Se considera SIEMPRE activa (ignora el checkbox enabled)
para evitar que al deshabilitarla el proveedor caiga silenciosamente al
default global que si rechaza.
"""

RULE_NO_ACTION = "no_action"
RULE_NO_PO = "no_po"
RULE_NO_RECEIPT = "no_receipt"
RULE_NO_PO_NO_RECEIPT = "no_po_no_receipt"

RULE_CODES = (RULE_NO_ACTION, RULE_NO_PO, RULE_NO_RECEIPT, RULE_NO_PO_NO_RECEIPT)

FINAL_STATES = ("A", "R")

import qp_supplier_front.uses_cases.documenteme.reject_retry

REJECT_PENDING_STATES = qp_supplier_front.uses_cases.documenteme.reject_retry.REJECT_PENDING_STATES

DEFAULT_MOTIVES = {
    RULE_NO_PO: (
        "Rechazo automático: la factura no coincide con ninguna "
        "orden de compra."
    ),
    RULE_NO_RECEIPT: (
        "Rechazo automático: la factura no coincide con ningún "
        "recibo de compra."
    ),
    RULE_NO_PO_NO_RECEIPT: (
        "Rechazo automático: la factura no coincide con ninguna "
        "orden de compra ni recibo de compra."
    ),
}


def is_active_rule(rule):
    if not rule:
        return False
    if rule.get("rule_code") == RULE_NO_ACTION:
        return True
    return (
        rule.get("rule_code") in RULE_CODES
        and bool(rule.get("enabled", 1))
    )


def resolve_auto_reject_config(supplier_rule, setup_default_rule):
    if is_active_rule(supplier_rule):
        return supplier_rule
    if is_active_rule(setup_default_rule):
        return setup_default_rule
    return None


def get_reject_motive(rule):
    motive = rule.get("motive")
    if motive:
        return motive
    return DEFAULT_MOTIVES.get(rule.get("rule_code"), DEFAULT_MOTIVES[RULE_NO_PO])


def has_po_match(invoice, po_exists_fn):
    purchase_order = invoice.get("nvfac_orde")
    if not purchase_order:
        return False
    return bool(po_exists_fn(purchase_order))


def has_receipt_match(invoice, receipt_for_po_fn):
    purchase_order = invoice.get("nvfac_orde")
    if not purchase_order:
        return False
    return receipt_for_po_fn(purchase_order) is not None


def should_auto_reject(po_match, receipt_match, rule_code):
    dispatch = {
        RULE_NO_ACTION: False,
        RULE_NO_PO: not po_match,
        RULE_NO_RECEIPT: not receipt_match,
        RULE_NO_PO_NO_RECEIPT: (not po_match) and (not receipt_match),
    }
    return bool(dispatch.get(rule_code, False))


def is_eligible_doc(doc):
    """Candidato a rechazo: sin evento final aplicado y en estado pendiente
    (E = evaluar regla, P = en proceso de rechazo)."""
    return (
        not doc.get("nvfac_ueve")
        and doc.get("nvfac_esta") in REJECT_PENDING_STATES
    )


def collect_rejectable(candidates, resolve_rule_fn, po_exists_fn, receipt_for_po_fn):
    rejectable = []
    for doc in candidates:
        if doc.get("nvfac_esta") == "PR":
            rejectable.append({
                "doc": doc,
                "rule": None,
                "pending": True,
            })
            continue
        rule = resolve_rule_fn(doc)
        if not is_active_rule(rule):
            continue
        po_match = has_po_match(doc, po_exists_fn)
        receipt_match = has_receipt_match(doc, receipt_for_po_fn)
        if should_auto_reject(po_match, receipt_match, rule.get("rule_code")):
            rejectable.append({"doc": doc, "rule": rule})
    return rejectable


def auto_reject(
    candidates_fn,
    resolve_rule_fn,
    po_exists_fn,
    receipt_for_po_fn,
    doc_names=None,
):
    candidates = []
    raw = candidates_fn() if doc_names is None else candidates_fn(doc_names)
    candidates = [doc for doc in raw if is_eligible_doc(doc)]
    rejectable = collect_rejectable(
        candidates, resolve_rule_fn, po_exists_fn, receipt_for_po_fn
    )
    return [
        {
            "doc": item["doc"].get("name") or item["doc"].get("nvfac_nume"),
            "motive": get_reject_motive(item["rule"]) if item.get("rule") else None,
            "rule": item["rule"].get("rule_name") if item.get("rule") else None,
            "pending": item.get("pending", False),
            "nvfac_conv": item["doc"].get("nvfac_conv"),
        }
        for item in rejectable
    ]
