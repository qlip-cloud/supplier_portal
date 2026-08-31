# -*- coding: utf-8 -*-
"""
documents_port.py (domain - ports)
==================================
Contrato de datos del flujo documenteme: persistencia en memoria (modo
simulador) o en la base de datos real (modo normal).

La capa de orquestacion (resources/uses_cases) depende de ESTE contrato, no
de Frappe ni del store en memoria. Cada operacion tiene dos implementaciones:
  - adaptador real: sobre frippe ORM (services/document_sync.py y lecturas
    directas existentes).
  - adaptador in-memory: sobre simulation/store.MemoryStore (sin base real).

No hay clase abstracta por compatibilidad Python 3.6. Las firmas documentadas
son la referencia del contrato.

Sync fases 1-2 (persistencia):
    create_sync_log(store|None, supplier_id, tax_id, endpoint_code, payload,
                    response, status) -> log_name
    create_sync_lines(store|None, log_name, ldocuments)
    get_uncompleted_lines(store|None) -> [line_dict]
    get_log_company_tax_id(store|None, log_name) -> tax_id
    create_document_detail(store|None, sync_line_name, document_data,
                           attached_list) -> doc_obj.con name
    log_sync_attempt(store|None, line_name, status, error_message, response)
    mark_line_completed(store|None, line_name)

Documentos (lectura/escritura para approve/reject/assign/confirmacion/view):
    query_documents(store|None, filters, fields, order_by, start, page_length,
                    pluck) -> [row]
    get_document(store|None, name) -> row_dict
    get_document_by_number(store|None, nvfac_nume, nvpro_ndoc) -> name
    set_document_value(store|None, name, field, value)
    update_document(store|None, name, fields)
    get_child_rows(store|None, child_doctype, parent) -> [row]
    get_assigned_line_names(store|None, user) -> [sync_line_name]
    count_documents(store|None, filters) -> int

Factura en BC / confirmacion:
    insert_purchase_invoice(store|None, doc, doc_number, now)
    find_purchase_invoice_by_invoice_id(store|None, invoice_id) -> name
    set_purchase_invoice_confirmation(store|None, invoice_id, confirmation_id)
    create_purchase_invoice_bc(store|None, doc_number, document_detail_name)

Referencias (datos de otros dominios; solo lectura en real, seeds en memoria):
    po_exists(store|None, purchase_order) -> bool
    get_headquarter(store|None, purchase_order) -> str
    receipts_total(store|None, purchase_order) -> number|None
    supplier_by_tax_id(store|None, tax_id) -> name|None
    supplier_auto_reject_rule(store|None, supplier) -> rule_name|None
    sede_exists(store|None, sede_code) -> bool
    user_exists(store|None, email) -> bool
    company_tax_id(store|None, company_name) -> tax_id
    master_setup_value(store|None, field) -> value

El primer parametro de cada funcion es el store en memoria (o None en el
adaptador real). El composition root (runtime.resolve()) decide que
implementacion inyecta.
"""