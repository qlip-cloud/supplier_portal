# -*- coding: utf-8 -*-
"""
documents_memory.py (documenteme simulation)
============================================
Implementacion in-memory del contrato domain/ports/documents_port.py sobre
simulation/store.MemoryStore. Misma semantica que services/document_sync.py
pero sin tocar la base de datos real.
"""

import base64
import json

LINE_FIELDS = [
    "nvfac_cont", "nvtip_docu", "nvfac_nume", "nvfac_cufe", "nvpro_nomb",
    "nvpro_ndoc", "nvfac_fech", "nvmon_codi", "nvfac_totp", "nvfac_esta",
    "nvfac_rfec", "nvfac_orde", "nvfac_rece", "nvfac_refe", "nvsuc_codi",
    "nvfac_venc", "nvfac_viva", "nvpro_ufac", "nvfac_vinc", "nvfac_vicb",
    "nvfac_ueve", "nvfac_stot", "nvfac_vicl", "nvfac_vinp", "nvfac_vibu",
    "nvfac_vicu", "nvfac_vadv",
]

DETAIL_FIELDS = [
    "nvfac_cont", "nvtip_docu", "nvfac_nume", "nvfac_cufe", "nvpro_nomb",
    "nvpro_ndoc", "nvfac_fech", "nvmon_codi", "nvfac_totp", "nvfac_esta",
    "nvfac_rfec", "nvfac_orde", "nvfac_rece", "nvfac_refe", "nvsuc_codi",
    "nvfac_venc", "nvfac_viva", "nvpro_ufac", "nvfac_ueve", "nvfac_stot",
    "nvfac_vinc", "nvfac_vicb", "nvfac_vicl", "nvfac_vinp", "nvfac_vibu",
    "nvfac_vicu", "nvfac_vadv", "nvfac_conv", "nvfac_fpag", "nvpro_cciu",
    "nvpro_ciud", "nvpro_cpai", "nvpro_pais", "nvpro_dire", "nvfac_tota",
    "nvfac_votr",
]

DETALLE_FIELDS = [
    "nvdet_cont", "nvpro_codi", "nvdet_desc", "nvdet_tcan", "nvdet_valo",
    "nvdet_stot", "nvdet_orde", "nvdet_rece", "nvdet_vdes", "nvuni_desc",
    "nvdet_nota",
]

TAX_FIELDS = ["nvimp_cdia", "nvimp_desc", "nvimp_base", "nvimp_valo", "nvimp_porc"]


def _src(field):
    """Clave fuente documenteme (Nvfac_esta etc.) desde el campo snake_case."""
    return field[:1].upper() + field[1:]


def _datetime(value):
    if value and isinstance(value, str) and len(value) >= 19:
        converted = value[:19].replace("T", " ")
        if converted.startswith("0001"):
            return None
        return converted
    return value


def _sync_line_name(nvpro_ndoc, nvfac_nume):
    if not nvpro_ndoc:
        return nvfac_nume
    return "{}:{}".format(nvpro_ndoc, nvfac_nume)


def _set_line_fields(log_name, doc_data):
    row = {"document_sync_log": log_name}
    for field in LINE_FIELDS:
        row[field] = doc_data.get(_src(field))
    row["nvfac_fech"] = _datetime(row.get("nvfac_fech"))
    row["nvfac_rfec"] = _datetime(row.get("nvfac_rfec"))
    row["nvfac_venc"] = _datetime(row.get("nvfac_venc"))
    row["nvpro_ufac"] = _datetime(row.get("nvpro_ufac"))
    row["is_completed"] = 0
    return row


class _DocRef(object):

    def __init__(self, name):
        self.name = name


def memory_create_sync_log(store, supplier_id, tax_id, endpoint_code,
                           payload, response, status):
    row = {
        "supplier": supplier_id,
        "tax_id": tax_id,
        "endpoint_code": endpoint_code,
        "payload": payload,
        "response": json.dumps(response) if not isinstance(response, str) else response,
        "status": "Success" if status == 200 else "Error",
    }
    if status != 200:
        if isinstance(response, dict):
            row["error_message"] = response.get("Description") or json.dumps(response)
        else:
            row["error_message"] = json.dumps(response)
    return store.insert("qp_SP_DocumentSyncLog", row)


def memory_create_sync_lines(store, log_name, ldocuments):
    for doc_data in (ldocuments or []):
        if doc_data.get("Nvfac_ueve"):
            continue
        nvfac_nume = doc_data.get("Nvfac_nume")
        name = _sync_line_name(doc_data.get("Nvpro_ndoc"), nvfac_nume)
        if store.exists("qp_SP_DocumentSyncLine", name):
            store.update("qp_SP_DocumentSyncLine", name,
                         _set_line_fields(log_name, doc_data))
        else:
            store.insert("qp_SP_DocumentSyncLine",
                         _set_line_fields(log_name, doc_data), name=name)


def memory_get_uncompleted_lines(store):
    return store.query(
        "qp_SP_DocumentSyncLine",
        filters={"is_completed": 0},
        fields=["name", "document_sync_log", "nvpro_ndoc", "nvfac_esta",
                "nvfac_nume"],
    )


def memory_get_log_company_tax_id(store, log_name):
    return store.get_value("qp_SP_DocumentSyncLog", log_name, "tax_id")


def memory_log_sync_attempt(store, line_name, status, error_message, response):
    row = {
        "parent": line_name,
        "attempt_date": _now_str(),
        "status": status,
        "error_message": error_message,
        "response": json.dumps(response) if not isinstance(response, str) else response,
    }
    store.insert("qp_SP_DetailSyncAttempt", row)


def memory_mark_line_completed(store, line_name):
    store.set_value("qp_SP_DocumentSyncLine", line_name, "is_completed", 1)


def _set_detail_fields(sync_line_name, document_data):
    row = {"document_sync_line": sync_line_name}
    for field in DETAIL_FIELDS:
        row[field] = document_data.get(_src(field))
    for attr in ("nvfac_fech", "nvfac_rfec", "nvfac_venc", "nvpro_ufac"):
        row[attr] = _datetime(row.get(attr))
    return row


def _build_detail_lines(store, parent, detalle):
    for item in (detalle or []):
        line = {"parent": parent, "parenttype": "qp_SP_DocumentDetail"}
        for field in DETALLE_FIELDS:
            line[field] = item.get(_src(field))
        store.insert("qp_SP_DetailLine", line)
        for impuesto in (item.get("lImpuestos") or []):
            tax = {"parent": parent, "parenttype": "qp_SP_DocumentDetail"}
            for field in TAX_FIELDS:
                tax[field] = impuesto.get(_src(field))
            store.insert("qp_SP_DetailLineTax", tax)


def _build_attached_files(store, parent, attached_list):
    for item in (attached_list or []):
        row = {"parent": parent, "parenttype": "qp_SP_DocumentDetail"}
        row["file_name"] = item.get("Nvdoc_nomb")
        row["file_type"] = item.get("Nvdoc_tipo")
        row["file_url"] = item.get("Nvdoc_nomb") or ""
        store.insert("qp_SP_DocumentAttach", row)


def _build_allowance_charges(store, parent, attached_list):
    from qp_supplier_front.services.xml_allowance_charge import (
        extract_document_allowance_charges,
    )

    for item in (attached_list or []):
        if item.get("Nvdoc_tipo") != "XML":
            continue
        file_content_b64 = item.get("Nvdoc_file")
        if not file_content_b64:
            continue
        try:
            xml_content = base64.b64decode(file_content_b64)
        except (TypeError, ValueError):
            continue
        for charge in extract_document_allowance_charges(xml_content):
            store.insert("qp_SP_AllowanceCharge", {
                "parent": parent,
                "parenttype": "qp_SP_DocumentDetail",
                "charge_indicator": charge.get("charge_indicator", 0),
                "reason_code": charge.get("reason_code"),
                "reason": charge.get("reason"),
                "multiplier_factor": charge.get("multiplier_factor"),
                "amount": charge.get("amount"),
                "currency": charge.get("currency"),
                "base_amount": charge.get("base_amount"),
            })


def memory_create_document_detail(store, sync_line_name, document_data,
                                  attached_list):
    nvfac_nume = document_data.get("Nvfac_nume")
    nvpro_ndoc = document_data.get("Nvpro_ndoc")
    name = _sync_line_name(nvpro_ndoc, nvfac_nume)

    doc = _set_detail_fields(sync_line_name, document_data)
    if store.exists("qp_SP_DocumentDetail", name):
        previous = store.get("qp_SP_DocumentDetail", name) or {}
        old_state = previous.get("nvfac_esta")
        new_state = doc.get("nvfac_esta")
        for child_doctype in ("qp_SP_DetailLine", "qp_SP_DetailLineTax",
                              "qp_SP_DocumentAttach", "qp_SP_AllowanceCharge"):
            for child in store.query(child_doctype, filters={"parent": name}):
                store.delete(child_doctype, child["name"])
        store.update("qp_SP_DocumentDetail", name, doc)
        if (old_state or "") != (new_state or ""):
            _memory_timeline(store).set_state(
                name, new_state, old_state=old_state
            )
    else:
        store.insert("qp_SP_DocumentDetail", doc, name=name)
        _memory_timeline(store).record_creation(name)

    _build_detail_lines(store, name, document_data.get("Detalle"))
    _build_attached_files(store, name, attached_list)
    _build_allowance_charges(store, name, attached_list)
    return _DocRef(name)


def memory_query_documents(store, filters, fields=None, order_by=None,
                           start=0, page_length=None, pluck=None, limit=None):
    return store.query(
        "qp_SP_DocumentDetail",
        filters=filters or {},
        fields=fields,
        order_by=order_by,
        start=start,
        page_length=page_length,
        pluck=pluck,
        limit=limit,
    )


def memory_get_document(store, name):
    return store.get("qp_SP_DocumentDetail", name)


def memory_get_document_by_number(store, nvfac_nume, nvpro_ndoc=None):
    filters = {"nvfac_nume": nvfac_nume}
    if nvpro_ndoc:
        filters["nvpro_ndoc"] = nvpro_ndoc
    rows = store.query("qp_SP_DocumentDetail", filters=filters, limit=1)
    return rows[0]["name"] if rows else None


def memory_set_document_value(store, name, field, value):
    store.set_value("qp_SP_DocumentDetail", name, field, value)


def memory_update_document(store, name, fields):
    store.update("qp_SP_DocumentDetail", name, fields)


def memory_get_child_rows(store, child_doctype, parent):
    return store.query(child_doctype, filters={"parent": parent})


def memory_get_assigned_line_names(store, user):
    names = set()
    for row in store.query("qp_SP_SyncLineAssignedUser",
                           filters={"user": user}):
        if row.get("parent"):
            names.add(row.get("parent"))
    for row in store.query("qp_SP_DocumentSyncLine",
                           filters={"assigned_to": user}):
        names.add(row.get("name"))
    return list(names)


def memory_count_documents(store, filters=None):
    return store.count("qp_SP_DocumentDetail", filters)


APPOINT_DOC_FIELDS = [
    "name", "nvfac_nume", "nvpro_ndoc", "nvfac_fech", "nvfac_cufe",
    "nvtip_docu", "nvfac_fpag", "nvfac_orde", "nvfac_rece", "nvfac_totp",
    "nvfac_esta", "nvfac_ueve", "nvfac_conv", "nvmon_codi", "nvfac_stot",
    "nvfac_viva", "nvpro_nomb",
]


def memory_get_docs(store, doc_names):
    return store.query(
        "qp_SP_DocumentDetail",
        filters={"name": ["in", list(doc_names or [])]},
        fields=APPOINT_DOC_FIELDS,
    )


def memory_get_lines(store, doc):
    rows = store.query("qp_SP_DetailLine",
                       filters={"parent": doc.get("name")})
    return [
        {
            "item_code": row.get("nvpro_codi") or "",
            "qty": row.get("nvdet_tcan") or 0,
            "rate": row.get("nvdet_valo") or 0,
            "idx": 0,
            "receiving_no": "",
            "order_no": doc.get("nvfac_orde") or "",
        }
        for row in rows
    ], ""


def memory_persist_invoice(store, doc, doc_number, now):
    if not doc_number:
        doc_number = doc.get("nvfac_nume") or doc.get("name")
    if store.exists("qp_SP_PurchaseInvoice", doc.get("name")):
        return doc_number
    now_str = now or _now_str()
    store.insert("qp_SP_PurchaseInvoice", {
        "name": doc.get("name"),
        "invoice_id": doc_number,
        "status": "Abierto",
        "supplier": None,
        "qp_sync_flow": "BC",
        "nvmon_codi": doc.get("nvmon_codi") or "COP",
        "nvfac_stot": doc.get("nvfac_stot") or 0,
        "nvfac_viva": doc.get("nvfac_viva") or 0,
        "nvfac_totp": doc.get("nvfac_totp") or 0,
        "creation": now_str,
        "modified": now_str,
    })
    store.insert("qp_SP_PurchaseInvoiceBC", {
        "invoice_id": doc_number,
        "purchase_invoice": doc.get("name"),
    }, name=doc_number)
    return doc_number


def memory_mark_registered(store, doc, doc_number=None):
    old_state = store.get_value(
        "qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta"
    )
    store.set_value("qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta", "BCC")
    _memory_timeline(store).set_state(
        doc.get("name"), "BCC", old_state=old_state
    )
    for alert in store.query("qp_SP_Alert", filters={"parent": doc.get("name")}):
        store.set_value("qp_SP_Alert", alert["name"], "status", "Resuelta")


def memory_mark_error(store, doc, error):
    store.insert("qp_SP_Alert", {
        "parent": doc.get("name"),
        "message": error or "",
        "creation": _now_str(),
    })


def memory_consume_receipts(store, doc, receipt_names):
    """Marca las recepciones asignadas con qp_invoice = nvfac_nume.

    Solo se consumen recepciones cuyo qp_invoice sigue vacio (evita doble
    consumo), replicando en memoria el UPDATE guardado del modo real.
    """
    if not receipt_names:
        return
    invoice_number = doc.get("nvfac_nume")
    if not invoice_number:
        return
    for name in receipt_names:
        row = store.get("qp_SP_PurchaseReceipt", name)
        if row and not row.get("qp_invoice"):
            store.set_value("qp_SP_PurchaseReceipt", name, "qp_invoice", invoice_number)


def memory_mark_duplicate_registered(store, doc, error, now):
    old_state = store.get_value(
        "qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta"
    )
    store.set_value("qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta", "BCC")
    _memory_timeline(store).set_state(
        doc.get("name"), "BCC", old_state=old_state
    )
    store.insert("qp_SP_Alert", {
        "parent": doc.get("name"),
        "alert_message": ("La factura ya existe en BC; se detuvo el reintento. "
                          "No se pudo obtener el codigo BC para enlazar su confirmacion. "
                          "Error: {}".format(error or "")),
        "alert_type": "ErrorUrgente",
        "status": "Abierta",
        "alert_date": now or _now_str(),
        "creation": now or _now_str(),
    })


def memory_find_document_by_invoice_id(store, invoice_id):
    if not invoice_id:
        return None
    names = store.query("qp_SP_PurchaseInvoice",
                        filters={"invoice_id": invoice_id}, pluck="name", limit=1)
    if not names:
        return None
    name = names[0]
    if not store.exists("qp_SP_DocumentDetail", name):
        return None
    return {"name": name, "invoice_id": invoice_id}


def memory_set_confirmation_id(store, doc, confirmation_id):
    invoice_id = doc.get("invoice_id")
    for row in store.query("qp_SP_PurchaseInvoice",
                           filters={"invoice_id": invoice_id}):
        store.set_value("qp_SP_PurchaseInvoice", row["name"],
                        "confirmation_id", confirmation_id)


def memory_mark_pending_approval(store, doc):
    old_state = store.get_value(
        "qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta"
    )
    store.set_value("qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta", "PA")
    _memory_timeline(store).set_state(
        doc.get("name"), "PA", old_state=old_state
    )


def memory_enqueue_approve(store, doc):
    """Cash: directo a A. Credito: secuencia 030/032/033 simulada -> A."""
    conv = store.get_value("qp_SP_DocumentDetail", doc.get("name"), "nvfac_conv")
    if str(conv) == "1":
        old_state = store.get_value(
            "qp_SP_DocumentDetail", doc.get("name"), "nvfac_esta"
        )
        store.set_value("qp_SP_DocumentDetail", doc.get("name"),
                        "nvfac_esta", "A")
        store.set_value("qp_SP_DocumentDetail", doc.get("name"),
                        "qp_is_event_completed", 1)
        _memory_timeline(store).set_state(
            doc.get("name"), "A",
            extra_fields={"qp_is_event_completed": 1},
            old_state=old_state,
        )
        for alert in store.query("qp_SP_Alert",
                                 filters={"parent": doc.get("name")}):
            store.set_value("qp_SP_Alert", alert["name"], "status", "Resuelta")
    else:
        memory_run_credit_confirmation(store, doc.get("name"))


def memory_run_credit_confirmation(store, doc_name):
    """Confirma la aprobacion credito en memoria: envia 030/032/033 (simulados)
    y marca A + nvfac_ueve 033 + resuelve alertas. Si algun evento falla, deja
    PA con alerta."""
    import json

    from qp_supplier_front.resources.documenteme import runtime
    from qp_supplier_front.uses_cases.documenteme.event_logs import (
        event_is_success,
        plan_event_log,
    )
    from qp_supplier_front.uses_cases.documenteme.event_notifier import (
        DOCUMENTEME_EVENT_STATES,
        _is_error,
    )

    components = runtime.resolve()
    company_tax_id = components["company_tax_id_fn"]()
    url, headers, method = components["event_endpoint_fn"]()
    event_http_fn = components["event_http_fn"]

    doc = store.get("qp_SP_DocumentDetail", doc_name) or {}

    for event_code in ("030", "032", "033"):
        payload = {
            "Nvemp_nnit": company_tax_id,
            "Nvpro_ndoc": doc.get("nvpro_ndoc"),
            "Nvfac_cont": doc.get("nvfac_cont"),
            "Nvfac_esta": DOCUMENTEME_EVENT_STATES.get(event_code, "E"),
            "Nveve_dian": event_code,
            "Nvint_desc": "Factura aprobada",
        }
        response, status = event_http_fn(payload, url, headers, method)
        now = _now_str()
        serialized = (
            json.dumps(response) if not isinstance(response, str) else response
        )
        existing = store.query(
            "qp_SP_EventLog",
            filters={"parent": doc_name, "event_code": event_code},
        )
        if plan_event_log(existing, event_is_success(response, status)) == "update":
            store.update("qp_SP_EventLog", existing[-1]["name"], {
                "status": status,
                "response": serialized,
                "attempt_date": now,
            })
        else:
            store.insert("qp_SP_EventLog", {
                "parent": doc_name,
                "event_code": event_code,
                "payload": json.dumps(payload),
                "response": serialized,
                "status": status,
                "attempt_date": now,
            })
        if _is_error(response, status):
            store.insert("qp_SP_Alert", {
                "parent": doc_name,
                "alert_message": ("No se ha podido notificar la aprobacion de {} "
                                  "en documenteme.".format(event_code)),
                "alert_type": "ErrorUrgente",
                "status": "Abierta",
                "alert_date": now,
                "creation": now,
            })
            return False

    old_state = store.get_value("qp_SP_DocumentDetail", doc_name, "nvfac_esta")
    store.set_value("qp_SP_DocumentDetail", doc_name, "nvfac_esta", "A")
    store.set_value("qp_SP_DocumentDetail", doc_name, "nvfac_ueve", "033")
    store.set_value("qp_SP_DocumentDetail", doc_name, "qp_is_event_completed", 1)
    _memory_timeline(store).set_state(
        doc_name, "A",
        extra_fields={"qp_is_event_completed": 1},
        old_state=old_state,
    )
    for alert in store.query("qp_SP_Alert", filters={"parent": doc_name}):
        store.set_value("qp_SP_Alert", alert["name"], "status", "Resuelta")
    return True


def memory_process_confirmation(store, invoice_id, confirmation_id):
    from qp_supplier_front.uses_cases.documenteme.approve_confirmation import (
        process_confirmation,
    )

    return process_confirmation(
        invoice_id,
        confirmation_id,
        find_document_fn=lambda doc_number: memory_find_document_by_invoice_id(
            store, doc_number),
        set_confirmation_id_fn=lambda doc, conf: memory_set_confirmation_id(
            store, doc, conf),
        mark_pending_approval_fn=lambda doc: memory_mark_pending_approval(
            store, doc),
        enqueue_approve_fn=lambda doc: memory_enqueue_approve(store, doc),
        commit_fn=lambda: None,
    )


def _memory_timeline(store):
    from qp_supplier_front.simulation.timeline_memory import MemoryTimelineAdapter
    return MemoryTimelineAdapter(store)


def _now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")