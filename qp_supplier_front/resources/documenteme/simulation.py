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
- La confirmacion de BC (confirmation_id) la ejecuta un actor automatismo:
  tras marcar "BCC" se reutiliza el nucleo puro process_confirmation para
  completar E -> V -> BCC -> PA -> A sin proceso externo.
- El sync de entrada (fases 1-2) se sirve de fixtures JSON en lugar de la
  API documenteme; el NIT de la compania es el NIT simulado para etiquetar
  las filas (limpieza manual por convencion).
- Los jobs de fondo (auto_reject y auto_approve_confirmation) no dependen de
  infraestructura externa: se simulan el endpoint y el NIT de la compania
  (get_event_endpoint / get_company_tax_id).

El resto del flujo (promover E->V, marcar BCC/PA/A/PR/R con event_logs,
persistencia local en qp_SP_PurchaseInvoice) se conserva intacto.

Este modulo tambien centraliza los factories de doubles (build_send_double,
build_http_double, build_inbound_sync_double) para que los endpoints
legacy *_mock (approve_mock / reject_mock / auto_approve_mock /
auto_reject_mock) y los tests unitarios reutilicen la misma logica.

La decision de usar este modulo o los adaptadores reales NO pertenece aqui:
vive en resources/documenteme/runtime.py (composition root), unico punto que
lee el flag qp_SP_MasterSetup.documenteme_simulation.
"""

import os


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


# =========================================================================
# Fixtures del sync de entrada
# =========================================================================
FIXTURES_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "documenteme_fixtures.json"
)


def load_fixtures(path=None):
    """Carga los fixtures JSON del sync simulado (fases 1-2).

    Retorna {"headers": [...], "details": {Nvfac_nume: {"Document": {...},
    "lAttached": [...]}}}. En ausencia del archivo devuelve un dict vacio.
    """
    import json

    fixture_path = path or FIXTURES_PATH
    try:
        with open(fixture_path, "r") as fh:
            data = json.load(fh)
    except (IOError, OSError, ValueError):
        return {"headers": [], "details": {}}
    return {
        "headers": list(data.get("headers") or []),
        "details": dict(data.get("details") or {}),
    }


def _extract_param_value(param, key):
    """Extrae el valor de un parametro de la query string de documenteme."""
    if not param:
        return None
    for chunk in str(param).split("&"):
        if chunk.startswith(key + "="):
            return chunk[len(key) + 1:]
    return None


def build_inbound_sync_double(headers=None, details=None,
                              fail_numes=None, fail_all=False):
    """Doble de la API documenteme para el sync de entrada (fases 1-2).

    Misma firma que send_request_status (endpoint_code, param,
    is_query_param) inyectado en sync_by_supplier y sync_detail.

    - headers: lista de dicts formato LDocuments (fase 1).
    - details: dict {Nvfac_nume: {"Document": {...}, "lAttached": [...]}}.
    - fail_numes: numeros (Nvfac_nume) cuyo detalle responde con error.
    - fail_all: el listado (fase 1) responde con error global.
    """
    from qp_supplier_front.constant.endpoint import (
        DOCUMENT_LIST_DOCUMENTS,
        DOCUMENT_DETAIL_DOCUMENT,
    )

    fail_set = set(fail_numes or [])

    def send_request_fn(endpoint_code=None, param=None, is_query_param=False):
        if fail_all:
            return {"Result": 1, "Description": "Error simulado en el listado"}, 200
        if endpoint_code == DOCUMENT_LIST_DOCUMENTS:
            return {"Result": 0, "LDocuments": list(headers or [])}, 200
        if endpoint_code == DOCUMENT_DETAIL_DOCUMENT:
            nume = _extract_param_value(param, "nvfac_nume")
            if nume and nume in fail_set:
                return {
                    "Result": 1,
                    "Description": "Error simulado en el detalle {}".format(nume),
                }, 200
            detail = (details or {}).get(nume) or {}
            document = detail.get("Document")
            if not document:
                return {
                    "Result": 1,
                    "Description": "No hay fixture para el detalle {}".format(nume),
                }, 200
            return {
                "Result": 0,
                "Document": document,
                "lAttached": detail.get("lAttached") or [],
            }, 200
        return {"Result": 1, "Description": "Endpoint no simulado"}, 200

    return send_request_fn


# =========================================================================
# Factories de doubles para aprobacion / eventos
# =========================================================================
def build_send_double(invoice_numbers=None, fail_numbers=None,
                      fail_all=False, simulate_duplicate=False):
    """send_request_fn simulado para la creacion en BC.

    Reemplaza el helper internino de approve_mock. El estado mutable usa
    un contador local del closure (no global) y es resetable por llamada.

    - invoice_numbers: doc_numbers a devolver por cada factura (mismo orden).
    - fail_numbers: facturas (NoFacturaProveedor) que devuelven error.
    - fail_all: error global (BC rechaza el lote completo).
    - simulate_duplicate: la 2da llamada devuelve duplicado (Result=1).
    """
    fail_set = set(fail_numbers or [])
    counters = {"approve": 0}

    def send_request_fn(endpoint_code=None, payload=None):
        if simulate_duplicate:
            counters["approve"] += 1
            if counters["approve"] > 1:
                return {"Result": 1, "Description": "Duplicado", "invoices": []}, 200

        if fail_all:
            return {
                "Result": 1,
                "Description": "Error global simulado al crear factura BC",
                "invoices": [],
            }, 200

        invoices = payload or []
        numbers = list(invoice_numbers or [])
        results = []
        for idx in range(len(invoices)):
            invoice = invoices[idx] if isinstance(invoices[idx], dict) else {}
            doc_number = invoice.get("NoFacturaProveedor") or "DOC{}".format(idx + 1)
            if doc_number in fail_set:
                results.append({
                    "doc_number": "",
                    "error": "Error simulado para la factura {}".format(doc_number),
                })
                continue
            doc_number = numbers[idx] if idx < len(numbers) else "SIM{}".format(doc_number)
            results.append({"doc_number": doc_number, "error": ""})
        return {"Result": 0, "invoices": results}, 200

    return send_request_fn


def build_http_double(fail_cont_numbers=None, fail_all=False,
                      already_applied=False, already_applied_once=False):
    """http_fn simulado para los lotes de eventos (rechazo y aprobacion).

    Reemplaza los helpers de auto_reject_mock / reject_mock. Mismo contrato
    que raw_http (payload, url, headers, method).

    - fail_cont_numbers: Nvfac_cont que siempre fallan (secuencia se corta).
    - fail_all: todas las facturas fallan.
    - already_applied: el evento devuelve "ya fue emitido" siempre.
    - already_applied_once: el 1er intento por evento devuelve "ya fue
      emitido" y los siguientes exito (replica reject_mock._build_test_sequence).
    """
    fail_set = set(fail_cont_numbers or [])
    attempts = {}

    def http_fn(payload, url, headers, method):
        cont = payload.get("Nvfac_cont") if payload else None
        if fail_all or (fail_set and cont in fail_set):
            return {"Result": 1, "Description": "Error simulado en el evento"}, 200

        event_code = payload.get("Nveve_dian") if payload else None
        if already_applied_once:
            key = event_code or "unknown"
            attempts[key] = attempts.get(key, 0) + 1
            if attempts[key] == 1:
                return {
                    "Result": 1,
                    "Description": "El evento {} ya fue emitido".format(event_code),
                }, 200
        if already_applied:
            return {
                "Result": 1,
                "Description": "El evento {} ya fue emitido".format(event_code or ""),
            }, 200

        return (
            {
                "Result": 0,
                "Description": "Estado de documento actualizado.",
                "Document": None,
                "lAttached": None,
            },
            200,
        )

    return http_fn


def build_confirmation_id(doc_number):
    """confirmation_id deterministico para el actor BC simulado."""
    return "SIMCONF-{}".format(doc_number)


def run_simulated_confirmation(approved, process_confirmation_fn=None):
    """Actor BC simulado: tras "BCC" carga confirmation_id y dispara la
    aprobacion en documenteme (secuencia 030/032/033).

    Reutiliza el nucleo puro process_confirmation con los callbacks reales
    de confirmation.py (por defecto). Devuelve la lista de resultados
    {doc_number, confirmation_id, ok}.

    process_confirmation_fn(doc_number, confirmation_id) se inyecta para
    poder probarse sin DB; retorna {"ok": bool, ...}.
    """
    if process_confirmation_fn is None:
        def process_confirmation_fn(doc_number, confirmation_id):
            from qp_supplier_front.resources.documenteme import confirmation
            from qp_supplier_front.uses_cases.documenteme.approve_confirmation import (
                process_confirmation,
            )
            return process_confirmation(
                doc_number,
                confirmation_id,
                find_document_fn=confirmation.find_document_by_invoice_id,
                set_confirmation_id_fn=confirmation.set_confirmation_id,
                mark_pending_approval_fn=confirmation.mark_pending_approval,
                enqueue_approve_fn=confirmation.enqueue_approve,
                commit_fn=confirmation._commit,
            )

    results = []
    for item in (approved or []):
        doc_number = item.get("doc_number")
        if not doc_number:
            continue
        confirmation_id = build_confirmation_id(doc_number)
        result = process_confirmation_fn(doc_number, confirmation_id)
        results.append({
            "doc_number": doc_number,
            "confirmation_id": confirmation_id,
            "ok": bool(result and result.get("ok")),
        })
    return results