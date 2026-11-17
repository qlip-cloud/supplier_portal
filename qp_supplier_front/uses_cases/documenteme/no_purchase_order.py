# -*- coding: utf-8 -*-
"""
no_purchase_order.py (documenteme)
==================================
Nucleo puro de la politica "factura de CREDITO sin OC".

Centraliza el unico punto de decision para que un cambio futuro de semantica
(por ejemplo, que un proveedor con `no_action` no se asigne) sea un cambio de
una constante y su test, no de varios modulos.

Reglas:
- Solo aplica a facturas de CREDITO. El CONTADO conserva su comportamiento
  actual (regla de rechazo -> asignar o aprobar).
- Excluye notas credito y delivery (no son facturas sin OC reales).
- "sin OC" = `nvfac_orde` vacio. Una OC que no existe o es de otro proveedor
  no entra a esta cola: sigue la regla de rechazo actual.
- Con el flag activo, la factura no se rechaza y se asigna a la fila catch-all
  de `qp_SP_AssignmentConfig` de su tipo de factura.

No importa Frappe. Todas las dependencias son parametros.
"""

from qp_supplier_front.uses_cases.documenteme.conversion import (
    is_cash_invoice,
    is_credit_note,
)
from qp_supplier_front.uses_cases.documenteme.purchase_orders import (
    parse_purchase_orders,
)

# Mismo literal que auto_reject.RULE_NO_ACTION. Se define local para no crear
# un ciclo de imports (auto_reject importa este modulo para el guard).
NO_ACTION = "no_action"

INVOICE_TYPE_ALL = "Todos"
INVOICE_TYPE_CREDIT = "Credito"
INVOICE_TYPE_CASH = "Contado"

# Knob de compatibilidad futura:
#   True  -> el flag asigna aunque el proveedor tenga `no_action` (semantica A,
#            decision de negocio actual).
#   False -> el `no_action` del proveedor tambien inhibe la asignacion.
DEFAULT_ASSIGN_WHEN_NO_ACTION = True


def has_purchase_orders(doc):
    """True si el documento trae al menos una OC en `nvfac_orde`."""
    return bool(parse_purchase_orders((doc or {}).get("nvfac_orde")))


def is_credit_doc(doc):
    """True si la factura es de credito (o sin conversion explicita)."""
    return not is_cash_invoice((doc or {}).get("nvfac_conv"))


def invoice_type_of(doc):
    """Tipo de factura para el filtro de configuracion de asignacion."""
    if is_cash_invoice((doc or {}).get("nvfac_conv")):
        return INVOICE_TYPE_CASH
    return INVOICE_TYPE_CREDIT


def is_without_po_credit(doc, is_delivery_fn=None):
    """True si es una factura de credito que llego sin OC."""
    doc = doc or {}
    if is_credit_note(doc.get("nvtip_docu")):
        return False
    if not is_credit_doc(doc):
        return False
    if is_delivery_fn is not None and is_delivery_fn(doc):
        return False
    return not has_purchase_orders(doc)


def is_pending_purchase_order(doc, enabled, assign_when_no_action=None,
                              supplier_rule=None, is_delivery_fn=None):
    """True si la factura entra a la cola "sin OC" (no rechazar y asignar).

    enabled: valor del flag `qp_SP_MasterSetup.assign_invoices_without_po`.
    assign_when_no_action: knob de semantica futura; por defecto toma
    DEFAULT_ASSIGN_WHEN_NO_ACTION.
    supplier_rule: regla de rechazo activa del proveedor (o default), solo se
    consulta cuando el knob es False.
    """
    if not enabled:
        return False
    if not is_without_po_credit(doc, is_delivery_fn=is_delivery_fn):
        return False

    if assign_when_no_action is None:
        assign_when_no_action = DEFAULT_ASSIGN_WHEN_NO_ACTION
    if not assign_when_no_action:
        if (supplier_rule or {}).get("rule_code") == NO_ACTION:
            return False
    return True


def should_assign_without_po(doc, enabled, assign_when_no_action=None,
                             supplier_rule=None, in_queue=True,
                             already_assigned=False, is_delivery_fn=None):
    """True si la factura debe asignarse a los destinatarios de "sin OC"."""
    if already_assigned or not in_queue:
        return False
    return is_pending_purchase_order(
        doc,
        enabled,
        assign_when_no_action=assign_when_no_action,
        supplier_rule=supplier_rule,
        is_delivery_fn=is_delivery_fn,
    )


def should_skip_reject_without_po(doc, enabled, assign_when_no_action=None,
                                  supplier_rule=None, is_delivery_fn=None):
    """True si la factura sin OC no debe entrar al rechazo automatico."""
    return is_pending_purchase_order(
        doc,
        enabled,
        assign_when_no_action=assign_when_no_action,
        supplier_rule=supplier_rule,
        is_delivery_fn=is_delivery_fn,
    )
