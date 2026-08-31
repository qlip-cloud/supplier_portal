# -*- coding: utf-8 -*-
"""
enrich_document_list.py
=======================
Service para enriquecer la lista de documentos de ventas (documenteme) con la
informacion que consume el template y el JS:

- detail_lines: lineas de detalle de la factura.
- allowance_charges: cargos/descuentos con running totals acumulado.
- attached_files: archivos adjuntos.
- non_xml_count: cantidad de adjuntos que no son XML.
- assigned_to_id / assigned_to_ids / assigned_to_name: asignacion del documento.

Mantiene la importacion lazy de frappe (dentro de las funciones que consultan
DB) para que el modulo se pueda importar sin Frappe instalado (testabilidad).
Las helpers de calculo puro estan separadas de las que consultan la base.
"""
from qp_supplier_front.services.enrich_document_detail import enrich_document_detail


NON_XML = "XML"
DEFAULT_ALLOWANCE_REASON = "Descuento/Cargo"
ASSIGNED_PREFIX = "Asignado a:"


def _data_api(data, name):
    """Retorna la funcion del facade (data) o de frappe real.

    Compatible con el facade (get_value en la instancia, db -> self) y con el
    objeto frappe/mock (db.get_value para lecturas de una columna).
    """
    if data is None:
        import frappe
        return frappe.db.get_value if name == "get_value" else frappe.get_all
    if name == "get_value" and hasattr(data, "db"):
        return data.db.get_value
    return getattr(data, name)


def enrich_document_list(documents, doctype, data=None):
    """Enriquece cada documento de la lista con la informacion de contexto.

    Con data (facade) lee de ahi (memoria en simulacion); sin data usa frappe.
    """
    for doc in documents:
        _enrich_doc(doc, doctype, data)
    return documents


def _enrich_doc(doc, doctype, data=None):
    _enrich_detail_lines(doc, doctype, data)
    _enrich_allowance_charges(doc, doctype, data)
    _enrich_attached_files(doc, doctype, data)
    _enrich_assignment(doc, data)
    if data is not None:
        enrich_document_detail(doc, data=data)
    else:
        enrich_document_detail(doc)


def _enrich_detail_lines(doc, doctype, data=None):
    """Carga las lineas de detalle de la factura en doc['detail_lines']."""
    doc["detail_lines"] = _data_api(data, "get_all")(
        "qp_SP_DetailLine",
        filters={"parent": doc["name"], "parenttype": doctype},
        fields=["nvpro_codi", "nvuni_desc", "nvdet_tcan", "nvdet_valo", "nvdet_vdes", "nvdet_stot"]
    )


def _enrich_allowance_charges(doc, doctype, data=None):
    """Carga los cargos/descuentos calculando signed_amount y running_total."""
    allowance_charges = _data_api(data, "get_all")(
        "qp_SP_AllowanceCharge",
        filters={"parent": doc["name"], "parenttype": doctype},
        fields=["reason", "amount", "charge_indicator"]
    )
    base_total = _sum_base_total(doc["detail_lines"])
    doc["allowance_charges"] = build_allowance_charges(allowance_charges, base_total)


def build_allowance_charges(allowance_charges, base_total):
    """Construye la lista de allowance charges con running total acumulado.

    Los registros sin monto se omiten. Para cada cargo se calcula el monto con
    signo (positivo si es cargo, negativo si es descuento) y se va acumulando
    sobre el total base de las lineas de detalle.
    """
    result = []
    running_total = base_total
    for ac in allowance_charges:
        if not ac.get("amount"):
            continue
        signed_amount = _signed_amount(ac.get("amount"), ac.get("charge_indicator"))
        running_total += signed_amount
        result.append({
            "reason": ac.get("reason") or DEFAULT_ALLOWANCE_REASON,
            "signed_amount": signed_amount,
            "running_total": running_total
        })
    return result


def _sum_base_total(detail_lines):
    """Suma el subtotal (nvdet_stot) de las lineas de detalle."""
    return sum(line.get("nvdet_stot") or 0 for line in detail_lines)


def _signed_amount(amount, charge_indicator):
    """Retorna el monto positivo (cargo) o negativo (descuento)."""
    if charge_indicator:
        return amount
    return -amount


def _enrich_attached_files(doc, doctype, data=None):
    """Carga los archivos adjuntos y cuenta los que no son XML."""
    doc["attached_files"] = _data_api(data, "get_all")(
        "qp_SP_DocumentAttach",
        filters={"parent": doc["name"], "parenttype": doctype},
        fields=["file_name", "file_type", "file_url", "file_id"]
    )
    doc["non_xml_count"] = count_non_xml(doc["attached_files"])


def count_non_xml(attached_files):
    """Cuenta los adjuntos cuyo file_type no es XML."""
    return len(
        [f for f in attached_files if f.get("file_type", "").upper() != NON_XML]
    )


def _enrich_assignment(doc, data=None):
    """Carga la asignacion del documento (ids, usuarios y nombres)."""
    assignee_id = _data_api(data, "get_value")(
        "qp_SP_DocumentSyncLine", doc.get("document_sync_line"), "assigned_to"
    )
    assigned_user_ids = _get_assigned_user_ids(data, doc, assignee_id)
    doc["assigned_to_id"] = assignee_id
    doc["assigned_to_ids"] = assigned_user_ids
    doc["assigned_to_name"] = build_assigned_to_name(data, assigned_user_ids)


def _get_assigned_user_ids(data, doc, assignee_id):
    """Retorna los usuarios de qp_SP_SyncLineAssignedUser; si no hay, usa assignee_id."""
    assigned_user_ids = [
        row.get("user")
        for row in _data_api(data, "get_all")(
            "qp_SP_SyncLineAssignedUser",
            filters={"parent": doc.get("document_sync_line"), "parenttype": "qp_SP_DocumentSyncLine"},
            fields=["user"]
        )
    ]
    if not assigned_user_ids and assignee_id:
        assigned_user_ids = [assignee_id]
    return assigned_user_ids


def build_assigned_to_name(data, assigned_user_ids):
    """Construye el texto 'Asignado a:\n- name1\n- name2' a partir de los ids."""
    if not assigned_user_ids:
        return None
    names = []
    for user_id in assigned_user_ids:
        names.append(_data_api(data, "get_value")("User", user_id, "full_name") or user_id)
    return ASSIGNED_PREFIX + "\n" + "\n".join("- " + name for name in names)
