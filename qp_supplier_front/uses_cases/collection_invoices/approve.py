# -*- coding: utf-8 -*-
"""
approve.py (uses_cases/collection_invoices)
===========================================
Orquestacion pura de la aprobacion de facturas de cuentas de cobro
(creacion en BC + marcado BCC). No importa Frappe.

Reutiliza el nucleo puro `approve_documents` de documenteme
(uses_cases/documenteme/approve.py) sin modificarlo: las unicas diferencias
son los callbacks inyectados (persistencia sobre qp_SP_PurchaseInvoice en
lugar de qp_SP_DocumentDetail) y que NO se encola ninguna notificacion a
documenteme (no hay on_batch_approved).
"""

from qp_supplier_front.uses_cases.documenteme.approve import (
    approve_documents,
    make_invoice_builder,
)


def approve_collection_invoices(
    doc_names,
    get_docs_fn,
    get_lines_fn,
    get_headquarter_fn,
    po_exists_fn,
    receipt_bank_fn,
    send_request_fn,
    parse_doc_numbers_fn,
    persist_invoice_fn,
    mark_registered_fn,
    mark_error_fn,
    commit_fn,
    now,
    mark_duplicate_registered_fn=None,
    consume_receipts_fn=None,
    force=False,
    resolve_rule_fn=None,
    build_invoice_fn=None,
):
    """Aprueba en lote las facturas de cuentas de cobro contra BC.

    Flujo (delegado en approve_documents):
    1. Valida cada factura (regla factura - OC - recepcion via receipt_bank).
       Con force=True se ignoran las advertencias de OC - recepcion - montos
       (los estados definitivos/en proceso siguen bloqueando).
    2. Resuelve las lineas (una por factura: primer item de la OC por el
       monto a facturar) y construye el payload BC.
    3. Envia el payload a BC (middleware create_purchase_invoices).
    4. Las facturas con doc_number se persisten y marcan "BCC"; las que
       fallan quedan en error (mark_error / mark_duplicate_registered).

    Retorna {"approved": [...], "errors": [...], "unregistrable": [...]}.
    """
    if build_invoice_fn is None:
        build_invoice_fn = make_invoice_builder("collection")
    return approve_documents(
        doc_names,
        get_docs_fn=get_docs_fn,
        get_lines_fn=get_lines_fn,
        get_headquarter_fn=get_headquarter_fn,
        po_exists_fn=po_exists_fn,
        receipt_bank_fn=receipt_bank_fn,
        send_request_fn=send_request_fn,
        parse_doc_numbers_fn=parse_doc_numbers_fn,
        persist_invoice_fn=persist_invoice_fn,
        mark_registered_fn=mark_registered_fn,
        mark_error_fn=mark_error_fn,
        mark_duplicate_registered_fn=mark_duplicate_registered_fn,
        consume_receipts_fn=consume_receipts_fn,
        commit_fn=commit_fn,
        now=now,
        force=force,
        resolve_rule_fn=resolve_rule_fn,
        build_invoice_fn=build_invoice_fn,
    )