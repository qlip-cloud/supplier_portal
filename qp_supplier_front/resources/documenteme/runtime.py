# -*- coding: utf-8 -*-
"""
runtime.py (documenteme) -- composition root
============================================
Unico punto donde el proceso documenteme decide si ejecutar con adaptadores
reales (documenteme, Business Central, middleware) o simulados.

Los orquestadores (resources/) y los casos de uso (uses_cases/) NO saben si
se esta simulando: piden su bundle de adaptadores via resolve() y lo aplican.
La decision (lectura del flag qp_SP_MasterSetup.documenteme_simulation) vive
unicamente en este modulo.
"""

from qp_supplier_front.resources.documenteme import simulation


def is_simulation_enabled():
    """True si el modo simulador documenteme esta activo en el setup."""
    import frappe
    return bool(frappe.db.get_single_value(
        "qp_SP_MasterSetup", "documenteme_simulation"
    ))


def _real_bundle():
    """Adaptadores reales: documenteme, Business Central y middleware."""
    from qp_authorization.use_case.basic.authorize import send_request_status
    from qp_supplier_front.resources.documenteme import _approve_base
    from qp_supplier_front.resources.documenteme import auto_reject
    from qp_supplier_front.infrastructure.adapters import documenteme_http_adapter
    from qp_supplier_front.services import document_sync
    from qp_supplier_front.simulation.data_facade import DataFacade
    from qp_supplier_front.uses_cases.documents import sync_all_whitelist

    return {
        "sync_send_fn": send_request_status,
        "sync_tax_id_fn": sync_all_whitelist.get_company_tax_id,
        "approve_send_fn": _approve_base.send_purchase_invoice_request,
        "event_http_fn": auto_reject.raw_http,
        "company_tax_id_fn": documenteme_http_adapter.get_company_tax_id,
        "event_endpoint_fn": documenteme_http_adapter.get_event_endpoint,
        "on_batch_approved_fn": None,
        "data": DataFacade(),
        "sync_persist": {
            "create_log": document_sync.create_sync_log,
            "create_lines": document_sync.create_sync_lines,
            "get_uncompleted_lines": document_sync.get_uncompleted_lines,
            "get_log_company_tax_id": document_sync.get_log_company_tax_id,
            "create_document_detail": document_sync.create_document_detail,
            "log_sync_attempt": document_sync.log_sync_attempt,
            "mark_line_completed": document_sync.mark_line_completed,
        },
    }


def _apply_simulated_confirmation(result):
    """Actor BC simulado: tras aprobar (BCC) carga confirmation_id via
    process_confirmation para completar E -> V -> BCC -> PA -> A sobre el
    store en memoria de la sesion."""
    from qp_supplier_front.simulation import documents_memory
    from qp_supplier_front.simulation import session

    store = session.store()
    process = (
        lambda invoice_id, confirmation_id: documents_memory
        .memory_process_confirmation(store, invoice_id, confirmation_id)
    )
    result["simulation_confirmation"] = simulation.run_simulated_confirmation(
        (result or {}).get("approved") or [],
        process_confirmation_fn=process,
    )


def _simulated_bundle():
    """Adaptadores simulados: sin efectos externos (documenteme / BC)."""
    from qp_supplier_front.simulation import data_facade
    from qp_supplier_front.simulation import documents_memory
    from qp_supplier_front.simulation import references_memory
    from qp_supplier_front.simulation import session

    fixtures = simulation.load_fixtures()
    store = session.store()

    def _bind(fn):
        def wrapped(*args, **kwargs):
            return fn(store, *args, **kwargs)
        return wrapped

    return {
        "sync_send_fn": simulation.build_inbound_sync_double(
            headers=fixtures.get("headers") or [],
            details=fixtures.get("details") or {},
        ),
        "sync_tax_id_fn": lambda _company_id: simulation.get_company_tax_id(),
        "approve_send_fn": simulation.send_purchase_invoice_request,
        "event_http_fn": simulation.http_event,
        "company_tax_id_fn": simulation.get_company_tax_id,
        "event_endpoint_fn": simulation.get_event_endpoint,
        "on_batch_approved_fn": _apply_simulated_confirmation,
        "data": data_facade.DataFacade(store=store),
        "approve_callbacks": {
            "get_docs_fn": _bind(documents_memory.memory_get_docs),
            "get_lines_fn": _bind(documents_memory.memory_get_lines),
            "get_headquarter_fn": _bind(
                references_memory.memory_get_headquarter),
            "po_exists_fn": _bind(references_memory.memory_po_exists),
            "receipts_total_fn": _bind(
                references_memory.memory_receipts_total),
            "persist_invoice_fn": _bind(
                documents_memory.memory_persist_invoice),
            "mark_registered_fn": _bind(
                documents_memory.memory_mark_registered),
            "mark_error_fn": _bind(documents_memory.memory_mark_error),
            "mark_duplicate_registered_fn": _bind(
                documents_memory.memory_mark_duplicate_registered),
            "get_supplier_by_tax_id_fn": _bind(
                references_memory.memory_get_supplier_by_tax_id),
            "resolve_rule_fn": lambda _doc: None,
        },
        "sync_persist": {
            "create_log": _bind(documents_memory.memory_create_sync_log),
            "create_lines": _bind(documents_memory.memory_create_sync_lines),
            "get_uncompleted_lines": _bind(
                documents_memory.memory_get_uncompleted_lines),
            "get_log_company_tax_id": _bind(
                documents_memory.memory_get_log_company_tax_id),
            "create_document_detail": _bind(
                documents_memory.memory_create_document_detail),
            "log_sync_attempt": _bind(
                documents_memory.memory_log_sync_attempt),
            "mark_line_completed": _bind(
                documents_memory.memory_mark_line_completed),
        },
        "_simulation_store": store,
    }


def resolve():
    """Adaptadores para ejecutar el flujo documenteme (real o simulado).

    Los consumidores obtienen solo las claves que necesitan y nunca deciden
    sobre simulacion. Unico punto de decision del flag.
    """
    if is_simulation_enabled():
        return _simulated_bundle()
    return _real_bundle()