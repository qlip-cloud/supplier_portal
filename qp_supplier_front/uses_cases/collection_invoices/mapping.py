# -*- coding: utf-8 -*-
"""
mapping.py (uses_cases/collection_invoices)
===========================================
Nucleo puro del flujo de facturas de compra generadas desde cuentas de cobro
(qp_SP_CollectionAccounts -> qp_SP_PurchaseInvoice).

Sin imports a Frappe. Reutiliza el nucleo puro de documenteme
(uses_cases/documenteme/approve.py) importando validate_registrable y
get_registrable_warnings: el flujo nuevo NO modifica el core de documenteme.

Responsabilidades:
- build_document_dict: convierte una fila de qp_SP_PurchaseInvoice en el dict
  con las claves que consume el core documenteme de aprobacion (misma forma
  que get_docs de _approve_base).
- build_single_line: linea BC unica a partir del primer item de la orden de
  compra y el monto a facturar de la cuenta de cobro.
- evaluate_document / collect_validation_violations: validacion de la regla
  factura - orden - recepcion adaptada, reutilizando el core documenteme.
"""

from qp_supplier_front.uses_cases.documenteme.approve import (
    get_registrable_warnings,
    validate_registrable,
)

CASH_PAYMENT_TYPE = "1"
CREDIT_PAYMENT_TYPE = "2"


def build_document_dict(purchase_invoice):
    """Convierte una fila de qp_SP_PurchaseInvoice en el dict documenteme.

    La fila (dict) puede venir del ORM de Frappe o del MemoryStore (mismo
    nombre de campos). El core de aprobacion de documenteme lee estas claves
    para validar, construir el payload BC y persistir.
    """
    purchase_invoice = purchase_invoice or {}

    name = purchase_invoice.get("name")
    return {
        "name": name,
        "nvfac_nume": purchase_invoice.get("nvfac_nume") or name,
        "nvpro_ndoc": purchase_invoice.get("nvpro_ndoc"),
        "nvfac_fech": purchase_invoice.get("nvfac_fech"),
        "nvfac_cufe": purchase_invoice.get("nvfac_cufe") or "",
        "nvfac_orde": purchase_invoice.get("purchase_order_id"),
        "nvfac_rece": purchase_invoice.get("nvfac_rece") or "",
        "nvfac_stot": purchase_invoice.get("subtotal") or 0,
        "nvfac_viva": purchase_invoice.get("tax") or 0,
        "nvfac_totp": purchase_invoice.get("total") or 0,
        "nvfac_conv": purchase_invoice.get("nvfac_conv") or CASH_PAYMENT_TYPE,
        "nvfac_esta": purchase_invoice.get("qp_status") or "E",
        "nvmon_codi": purchase_invoice.get("currency") or "COP",
        "collection_account": purchase_invoice.get("collection_account"),
    }


def build_single_line(first_po_item, amount_payable, order_no=""):
    """Genera la unica linea BC de la factura de cuenta de cobro.

    Por requerimiento, la linea toma SOLO el primer item de la orden de
    compra y su valor total es el monto a facturar (qty=1, rate=monto).
    """
    first_po_item = first_po_item or {}
    return {
        "item_code": first_po_item.get("item_code") or "",
        "qty": 1,
        "rate": float(amount_payable or 0),
        "idx": 0,
        "receiving_no": "",
        "order_no": order_no or "",
    }


def evaluate_document(doc, po_exists_fn, receipt_bank_fn, resolve_rule_fn=None):
    """Valida una factura de cuenta de cobro (tratada como CONTADO).

    Reusa validate_registrable del nucleo documenteme: las facturas de contado
    no exigen OC/recibos salvo que la regla de rechazo activa
    (resolve_rule_fn, Supplier.auto_reject con fallback MasterSetup) lo exija;
    en ese caso la factura debe cumplirla para quedar en "V". Retorna (ok, error).
    """
    return validate_registrable(
        doc,
        po_exists_fn,
        receipt_bank_fn,
        resolve_rule_fn=resolve_rule_fn,
    )


def collect_validation_violations(docs, po_exists_fn, receipt_bank_fn,
                                  resolve_rule_fn=None):
    """Acumula las violaciones de aprobacion automatica por factura.

    Retorna [{"nvfac_nume", "violations": [mensaje, ...]}] para las facturas
    que no cumplen la regla; misma forma que collect_registrable_violations
    del flujo documenteme (reusado por el front en el confirm de aprobacion).
    """
    violations = []
    for doc in (docs or []):
        warnings = get_registrable_warnings(
            doc,
            po_exists_fn,
            receipt_bank_fn,
            resolve_rule_fn=resolve_rule_fn,
        )
        if warnings:
            violations.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "violations": warnings,
            })
    return violations