# -*- coding: utf-8 -*-
"""
attachments.py (documenteme) - infraestructura
==============================================
Adjuntos de facturas documenteme desde el front:

  - get_attachments(doc_name): lista los adjuntos y si hay al menos uno
    descargable (no XML) con archivo fisico. El front usa `has_downloadable`
    para decidir entre descargar o abrir el modal de carga.
  - add_attachment(doc_name, file_id, file_url, file_name): registra en el
    child `attached_files` un File ya subido por el front (`upload_file`).
    Idempotente: no duplica por file_id ni por file_url.

El control de acceso reutiliza el mismo filtro de asignacion de la lista
(`documenteme_access.get_assigned_sync_lines_filters`). La fila del child se
inserta directo (patron de timeline_adapter._insert_row) para no re-disparar
hooks ni revalidar el padre.
"""

import frappe

from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.documenteme_access import (
    get_assigned_sync_line_names,
    get_assigned_sync_lines_filters,
)
from qp_supplier_front.uses_cases.documenteme.attachments import (
    build_attachment_row,
    count_non_xml,
    has_downloadable,
    plan_attachment,
)
from qp_supplier_front.uses_cases.documenteme.notification_state import (
    is_locked,
)

DOCUMENT_DETAIL = "qp_SP_DocumentDetail"
ATTACH_DOCTYPE = "qp_SP_DocumentAttach"
ATTACH_PARENTFIELD = "attached_files"
ATTACH_FIELDS = ["file_name", "file_type", "file_url", "file_id"]


def _clean(value):
    return str(value or "").strip()


def _access_filters(doc_name, data=None):
    if data is not None:
        assigned_fn = lambda user: get_assigned_sync_line_names(user, data=data)
    else:
        assigned_fn = get_assigned_sync_line_names
    return get_assigned_sync_lines_filters(
        frappe.get_roles(), frappe.session.user, assigned_fn, {"name": doc_name}
    )


def _can_access(doc_name, data=None):
    if data is not None:
        rows = data.get_all(
            DOCUMENT_DETAIL, filters=_access_filters(doc_name, data),
            pluck="name", limit=1,
        )
        return bool(rows)
    rows = frappe.get_all(
        DOCUMENT_DETAIL, filters=_access_filters(doc_name),
        pluck="name", limit=1,
    )
    return bool(rows)


def _detail_exists(doc_name):
    return bool(frappe.db.exists(DOCUMENT_DETAIL, doc_name))


def _detail_state(doc_name, data=None):
    if data is not None:
        return data.get_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta") or ""
    return frappe.db.get_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta") or ""



def _get_rows(doc_name, data=None):
    if data is not None:
        return data.get_all(
            ATTACH_DOCTYPE,
            filters={"parent": doc_name, "parenttype": DOCUMENT_DETAIL},
            fields=ATTACH_FIELDS,
        )
    return frappe.get_all(
        ATTACH_DOCTYPE,
        filters={"parent": doc_name, "parenttype": DOCUMENT_DETAIL},
        fields=ATTACH_FIELDS,
    )


def _exists_on_disk(row):
    file_id = _clean(row.get("file_id"))
    if not file_id:
        return False
    try:
        return bool(frappe.get_doc("File", file_id).exists_on_disk())
    except Exception:
        return False


def _insert_attach_row(doc_name, row):
    """Child insert directo: no re-guarda ni revalida el padre."""
    last = frappe.db.sql(
        """
        SELECT COALESCE(MAX(idx), 0)
        FROM `tabqp_SP_DocumentAttach`
        WHERE parent = %s AND parenttype = %s
        """,
        (doc_name, DOCUMENT_DETAIL),
    ) or [[0]]
    idx = int((last[0][0] or 0)) + 1
    row_name = frappe.generate_hash(length=10)
    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_DocumentAttach`
        (name, parent, parentfield, parenttype, idx, file_name, file_type,
         file_url, file_id, creation, modified, modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
        """,
        (
            row_name, doc_name, ATTACH_PARENTFIELD, DOCUMENT_DETAIL, idx,
            row.get("file_name"), row.get("file_type"), row.get("file_url"),
            row.get("file_id"), frappe.session.user, frappe.session.user,
        ),
    )
    return dict(row, name=row_name, idx=idx)


def _resolve_file(file_id=None, file_url=None, file_name=None):
    """File de Frappe que el front subio con upload_file."""
    file_id = _clean(file_id)
    file_url = _clean(file_url)
    if file_id:
        try:
            return frappe.get_doc("File", file_id)
        except Exception:
            return None
    if file_url:
        found = frappe.db.get_value("File", {"file_url": file_url}, "name")
        if found:
            try:
                return frappe.get_doc("File", found)
            except Exception:
                return None
    return None


def _can_use_file(file_doc):
    """Evita adjuntar carpetas o archivos privados de otro usuario."""
    if file_doc.get("is_folder"):
        return False
    if file_doc.get("is_private") and file_doc.get("owner") != frappe.session.user:
        return False
    return True



def _response_data(rows, data=None):
    exists_fn = (
        (lambda row: bool(_clean(row.get("file_id"))))
        if data is not None
        else _exists_on_disk
    )
    return {
        "attachments": rows,
        "count": len(rows),
        "non_xml_count": count_non_xml(rows),
        "has_downloadable": has_downloadable(rows, exists_fn=exists_fn),
    }


@frappe.whitelist()
def get_attachments(doc_name):
    try:
        doc_name = _clean(doc_name)
        if not doc_name:
            response(400, "Falta el documento")
            return None
        data = runtime.resolve().get("data")
        if data is not None:
            if not _can_access(doc_name, data):
                response(403, "No tiene acceso a la factura")
                return None
        elif not _detail_exists(doc_name) or not _can_access(doc_name):
            response(403, "No tiene acceso a la factura")
            return None

        rows = _get_rows(doc_name, data)
        response(200, "", data=_response_data(rows, data))
        return None
    except Exception as error:
        response(500, "Error al obtener los adjuntos: {}".format(str(error)))
        return None


@frappe.whitelist()
def add_attachment(doc_name, file_id=None, file_url=None, file_name=None):
    try:
        doc_name = _clean(doc_name)
        if not doc_name:
            response(400, "Falta el documento")
            return None
        data = runtime.resolve().get("data")
        if data is not None:
            if not _can_access(doc_name, data):
                response(403, "No tiene acceso a la factura")
                return None
        elif not _detail_exists(doc_name) or not _can_access(doc_name):
            response(403, "No tiene acceso a la factura")
            return None

        if is_locked(_detail_state(doc_name, data)):
            response(
                400,
                "La factura está cerrada y no admite adjuntos",
            )
            return None

        file_doc = _resolve_file(file_id, file_url, file_name)
        if file_doc is None:
            response(400, "No se encontro el archivo cargado")
            return None
        if not _can_use_file(file_doc):
            response(403, "No tiene permiso sobre el archivo")
            return None

        row = build_attachment_row(
            file_doc.get("file_name") or file_name,
            file_doc.get("file_url") or file_url,
            file_doc.get("name") or file_id,
        )
        if not row.get("file_url"):
            response(400, "El archivo no tiene URL")
            return None

        current = _get_rows(doc_name, data)
        to_add, existing = plan_attachment(current, row)
        if existing is not None:
            response(200, "", data=_response_data(current, data))
            return None

        if data is not None:
            data.insert_child(ATTACH_DOCTYPE, doc_name, dict(
                to_add,
                parentfield=ATTACH_PARENTFIELD,
                parenttype=DOCUMENT_DETAIL,
            ))
            data.commit()
        else:
            _insert_attach_row(doc_name, to_add)
            frappe.db.commit()

        rows = _get_rows(doc_name, data)
        response(200, "", data=_response_data(rows, data))
        return None
    except Exception as error:
        response(500, "Error al guardar el adjunto: {}".format(str(error)))
        return None
