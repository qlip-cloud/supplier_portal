# -*- coding: utf-8 -*-
"""
runtime.py (resources/collection_accounts) -- composition root
==============================================================
Unico punto donde el flujo de cuentas de cobro - facturas de compra decide si
ejecutar con adaptadores reales (Business Central, middleware, Frappe) o
simulados (memoria).

Los orquestadores (resources/) y los casos de uso (uses_cases/) NO saben si
se esta simulando: piden su bundle de adaptadores via resolve() y lo aplican.
La decision (lectura del flag qp_SP_MasterSetup.collection_invoices_simulation)
vive unicamente en este modulo.

En modo real NO se usa el facade de datos (data): los flujos llaman a frappe
directamente. En modo simulado data es un DataFacade sobre el MemoryStore de
la sesion y las operaciones se resuelven en memoria.
"""

from qp_supplier_front.resources.collection_accounts import (
    _collection_invoice_base,
)


def is_simulation_enabled():
    """True si el modo simulador del flujo de cuentas de cobro esta activo.

    Si el flag no puede leerse (campo ausente, tabla inexistente o error de
    lectura) se asume que la simulacion NO esta activa (modo real) y se
    loguea, en lugar de tumbar el flujo.
    """
    import frappe

    try:
        return bool(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "collection_invoices_simulation"
        ))
    except Exception:
        try:
            frappe.log_error(
                message=frappe.get_traceback(),
                title="collection_invoices is_simulation_enabled",
            )
        except Exception:
            pass
        return False


def _real_bundle():
    """Adaptadores reales: Frappe + middleware BC."""
    base = _collection_invoice_base
    return {
        "data": None,
        "send_request_fn": base.send_purchase_invoice_request,
        "approve_callbacks": {
            "get_docs_fn": base.get_docs,
            "get_lines_fn": base.get_lines,
            "get_headquarter_fn": base.get_headquarter,
            "po_exists_fn": base.po_exists,
            "receipt_bank_fn": base.receipt_bank,
            "consume_receipts_fn": base.consume_receipts,
            "persist_invoice_fn": base.persist_invoice,
            "mark_registered_fn": base.mark_registered,
            "mark_error_fn": base.mark_error,
            "mark_duplicate_registered_fn": base.mark_duplicate_registered,
            "resolve_rule_fn": base.resolve_rule,
        },
        "evaluate_callbacks": {
            "po_exists_fn": base.po_exists,
            "receipt_bank_fn": base.receipt_bank,
            "resolve_rule_fn": base.resolve_rule,
        },
        "reject_fn": base.reject,
        "set_confirmation_fn": base.set_confirmation,
        "create_account_fn": None,
        "on_batch_approved_fn": None,
    }


def _simulated_bundle():
    """Adaptadores simulados: sin efectos externos (Business Central / DB)."""
    from qp_supplier_front.infrastructure.adapters import data_facade
    from qp_supplier_front.resources.documenteme import simulation
    from qp_supplier_front.simulation import (
        collection_invoices_memory,
        collection_seeds,
        documents_memory,
        references_memory,
        session,
    )

    store = session.store()
    collection_seeds.seed_collection_scenario(store)

    def _bind(fn):
        def wrapped(*args, **kwargs):
            return fn(store, *args, **kwargs)
        return wrapped

    return {
        "data": data_facade.DataFacade(store=store),
        "send_request_fn": simulation.send_purchase_invoice_request,
        "approve_callbacks": {
            "get_docs_fn": _bind(collection_invoices_memory.memory_get_docs),
            "get_lines_fn": _bind(
                collection_invoices_memory.memory_get_lines),
            "get_headquarter_fn": _bind(
                references_memory.memory_get_headquarter),
            "po_exists_fn": _bind(references_memory.memory_po_exists),
            "receipt_bank_fn": _bind(
                references_memory.memory_get_receipt_bank),
            "consume_receipts_fn": _bind(
                documents_memory.memory_consume_receipts),
            "persist_invoice_fn": _bind(
                collection_invoices_memory.memory_persist_invoice),
            "mark_registered_fn": _bind(
                collection_invoices_memory.memory_mark_registered),
            "mark_error_fn": _bind(
                collection_invoices_memory.memory_mark_error),
            "mark_duplicate_registered_fn": _bind(
                collection_invoices_memory.memory_mark_duplicate_registered),
            "resolve_rule_fn": _bind(references_memory.memory_resolve_rule),
        },
        "evaluate_callbacks": {
            "po_exists_fn": _bind(references_memory.memory_po_exists),
            "receipt_bank_fn": _bind(
                references_memory.memory_get_receipt_bank),
            "resolve_rule_fn": _bind(references_memory.memory_resolve_rule),
        },
        "reject_fn": _bind(collection_invoices_memory.memory_reject),
        "set_confirmation_fn": _bind(
            collection_invoices_memory.memory_set_confirmation),
        "create_account_fn": _bind(
            collection_invoices_memory.memory_create_collection_account),
        "on_batch_approved_fn": None,
        "_simulation_store": store,
    }


def resolve():
    """Adaptadores para ejecutar el flujo (real o simulado).

    Los consumidores obtienen solo las claves que necesitan y nunca deciden
    sobre simulacion. Unico punto de decision del flag.
    """
    if is_simulation_enabled():
        return _simulated_bundle()
    return _real_bundle()