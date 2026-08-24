# -*- coding: utf-8 -*-
"""
simulation.py (documenteme)
===========================
Modo simulador para el flujo documenteme.

Cuando qp_SP_MasterSetup.documenteme_simulation esta activo, los flujos de
aprobacion y rechazo (manual y automatico) se ejecutan completos pero sin
efectos externos:

- No se crea la factura en BC (se simula una respuesta exitosa con
  doc_number por cada factura del payload).
- No se notifica a documenteme: la secuencia 030 -> 032 -> 031 (rechazo) y
  la secuencia 030 -> 032 -> 033 (aprobacion) devuelven una respuesta de
  exito simulada.
- Los jobs de fondo (auto_reject y auto_approve_confirmation) no dependen de
  infraestructura externa: se simulan el endpoint y el NIT de la compania
  (get_event_endpoint / get_company_tax_id).

El resto del flujo (promover E->V, marcar BCC/PA/A/PR/R con event_logs,
persistencia local en qp_SP_PurchaseInvoice) se conserva intacto.
"""


def is_simulation_enabled():
    """True si el modo simulador documenteme esta activo en el setup."""
    import frappe
    return bool(frappe.db.get_single_value(
        "qp_SP_MasterSetup", "documenteme_simulation"
    ))


def _sim_doc_number(invoice, idx):
    """Numero de documento BC simulado y deterministico por factura."""
    for key in ("NoFacturaProveedor",):
        value = (invoice or {}).get(key)
        if value:
            return "SIM{}".format(value)
    return "SIM{}".format(idx + 1)


def send_purchase_invoice_request(endpoint_code=None, payload=None):
    """Simula la creacion exitosa de facturas en BC.

    Devuelve un resultado por factura (mismo orden del payload) con un
    doc_number simulado, evitando cualquier llamada OData de resolucion.
    """
    invoices = payload or []
    results = [
        {"doc_number": _sim_doc_number(invoice, idx), "error": ""}
        for idx, invoice in enumerate(invoices)
    ]
    return {"Result": 0, "invoices": results}, 200


def send_event_request(endpoint_code=None, payload=None):
    """Simula una notificacion exitosa de estado a documenteme."""
    return (
        {
            "Result": 0,
            "Description": "Estado de documento actualizado (simulado).",
            "Document": None,
            "lAttached": None,
        },
        200,
    )


def http_event(payload, url, headers, method):
    """http_fn simulado para los lotes de rechazo/aprobacion (misma firma que raw_http)."""
    return send_event_request(payload=payload)


SIMULATED_COMPANY_TAX_ID = "999999999"


def get_company_tax_id():
    """NIT simulado de la compania para evitar leer Company en modo simulacion."""
    return SIMULATED_COMPANY_TAX_ID


def get_event_endpoint():
    """Endpoint simulado para los jobs de fondo (misma firma que auto_reject/
    auto_approve_confirmation.get_event_endpoint) sin depender de qp_authorization."""
    return ("https://simulation.local/documenteme/event", {}, "POST")