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
        line = {"parent": parent}
        for field in DETALLE_FIELDS:
            line[field] = item.get(_src(field))
        store.insert("qp_SP_DetailLine", line)
        for impuesto in (item.get("lImpuestos") or []):
            tax = {"parent": parent}
            for field in TAX_FIELDS:
                tax[field] = impuesto.get(_src(field))
            store.insert("qp_SP_DetailLineTax", tax)


def _build_attached_files(store, parent, attached_list):
    for item in (attached_list or []):
        row = {"parent": parent}
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
        for child_doctype in ("qp_SP_DetailLine", "qp_SP_DetailLineTax",
                              "qp_SP_DocumentAttach", "qp_SP_AllowanceCharge"):
            for child in store.query(child_doctype, filters={"parent": name}):
                store.delete(child_doctype, child["name"])
        store.update("qp_SP_DocumentDetail", name, doc)
    else:
        store.insert("qp_SP_DocumentDetail", doc, name=name)

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


def _now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")