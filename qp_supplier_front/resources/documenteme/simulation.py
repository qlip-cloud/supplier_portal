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
- No se notifica el rechazo a documenteme (la secuencia 030 -> 032 -> 031
  devuelve una respuesta de exito simulada).

El resto del flujo (promover E->V->A, marcar R con motive, event_logs,
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
    """http_fn simulado para el lote de auto-rechazo (misma firma que raw_http)."""
    return send_event_request(payload=payload)