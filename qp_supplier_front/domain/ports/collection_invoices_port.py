# -*- coding: utf-8 -*-
"""
collection_invoices_port.py (domain - ports)
=============================================
Contrato de datos del flujo "Cuentas de Cobro -> Facturas de Compra"
(qp_SP_CollectionAccounts -> qp_SP_PurchaseInvoice).

Replica el patron de domain/ports/documents_port.py: la capa de orquestacion
(resources/uses_cases) depende de ESTE contrato, no de Frappe ni del store en
memoria. Cada operacion tiene dos implementaciones:
  - adaptador real: sobre el ORM de Frappe.
  - adaptador in-memory: sobre simulation/store.MemoryStore (modo simulador).

No hay clase abstracta por compatibilidad Python 3.6. Las firmas documentadas
son la referencia del contrato.

El primer parametro de cada funcion es el store en memoria (o None en el
adaptador real). El composition root (resources/collection_accounts/runtime.py)
decide que implementacion inyecta.

Creacion de cuenta de cobro / factura:
    create_collection_account(store|None, purchase_order, amount_to_invoice,
                              observations, docs) -> {name, purchase_invoice}
    create_purchase_invoice(store|None, collection_account_row) -> pi_name
    evaluate_purchase_invoice(store|None, pi_name) -> {"ok", "warnings"}

Aprobacion / rechazo (usa el nucleo puro de documenteme approve_documents):
    get_docs(store|None, doc_names) -> [document_dict]
    get_lines(store|None, doc) -> (lines, error)
    po_exists(store|None, purchase_order) -> bool
    get_headquarter(store|None, purchase_order) -> str
    receipt_bank(store|None, purchase_order) -> [receipt_dict]
    consume_receipts(store|None, doc, receipt_names)
    persist_invoice(store|None, doc, doc_number, now) -> doc_number
    mark_registered(store|None, doc, doc_number)
    mark_error(store|None, doc, error)
    mark_duplicate_registered(store|None, doc, error, now)

Rechazo / confirmacion:
    reject_invoice(store|None, doc_names, motive, is_invoice_error)
    set_confirmation(store|None, invoice_id, confirmation_id)

Consulta (vista):
    query_purchase_invoices(store|None, filters, fields, order_by, start,
                            page_length) -> [row]
    get_purchase_invoice(store|None, name) -> row_dict

Referencias (datos de otros dominios; solo lectura en real, seeds en memoria):
    po_exists(store|None, purchase_order) -> bool
    get_headquarter(store|None, purchase_order) -> str
    receipt_bank(store|None, purchase_order) -> [receipt_dict]
"""