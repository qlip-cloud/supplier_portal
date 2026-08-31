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
    from qp_supplier_front.uses_cases.documents import sync_all_whitelist

    return {
        "sync_send_fn": send_request_status,
        "sync_tax_id_fn": sync_all_whitelist.get_company_tax_id,
        "approve_send_fn": _approve_base.send_purchase_invoice_request,
        "event_http_fn": auto_reject.raw_http,
        "company_tax_id_fn": documenteme_http_adapter.get_company_tax_id,
        "event_endpoint_fn": documenteme_http_adapter.get_event_endpoint,
        "on_batch_approved_fn": None,
    }


def _apply_simulated_confirmation(result):
    """Actor BC simulado: tras aprobar (BCC) carga confirmation_id via
    process_confirmation para completar E -> V -> BCC -> PA -> A."""
    result["simulation_confirmation"] = simulation.run_simulated_confirmation(
        (result or {}).get("approved") or []
    )


def _simulated_bundle():
    """Adaptadores simulados: sin efectos externos (documenteme / BC)."""
    fixtures = simulation.load_fixtures()
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
    }


def resolve():
    """Adaptadores para ejecutar el flujo documenteme (real o simulado).

    Los consumidores obtienen solo las claves que necesitan y nunca deciden
    sobre simulacion. Unico punto de decision del flag.
    """
    if is_simulation_enabled():
        return _simulated_bundle()
    return _real_bundle()