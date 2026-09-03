# -*- coding: utf-8 -*-
"""
timeline_adapter.py (infrastructure - timeline data adapter)
=============================================================
Adaptador real del timeline de facturas documenteme: lee y persiste las
entradas del historial sobre frappe (qp_SP_TimelineEntry, child de
qp_SP_DocumentDetail) y fusiona los event_logs de documenteme
(qp_SP_EventLog).

Implementa el contrato de domain/ports/timeline_port.py. La contraparte
in-memory es simulation/timeline_memory.py (MemoryTimelineAdapter).

Las escrituras de estado (set_state) persisten como lo hacian originalmente
los sitios de transicion (frappe.db.set_value) y agregan la fila del timeline
como child insert directo (mismo patron que _alerts.insert_alert), SIN
re-save del padre: asi no se dispara el hook before_save y se evita duplicar
la entrada de estado.

El modulo de frappe es inyectable (como RealMasterSetupSource) para que los
tests puedan delegar en su propio mock; por defecto se usa el frappe real.
"""

from qp_supplier_front.uses_cases.documenteme.timeline import (
    ENTRY_COMMENT,
    build_comment_entry,
    build_creation_entry,
    build_state_entry,
    order_desc,
)

DOCUMENT_DETAIL = "qp_SP_DocumentDetail"
TIMELINE_ENTRY = "qp_SP_TimelineEntry"
TIMELINE_READ = "qp_SP_TimelineRead"


def _resolve_frappe(frappe=None):
    if frappe is not None:
        return frappe
    import frappe
    return frappe


def _user_name(user=None, frappe=None):
    frappe = _resolve_frappe(frappe)
    user_id = user or getattr(frappe.session, "user", "Administrator")
    try:
        return frappe.utils.get_fullname(user_id) or user_id
    except Exception:
        return user_id


def _now_str(now=None):
    if now:
        return now
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _insert_row(parent_name, entry, frappe=None):
    """Inserta una fila del timeline como child de qp_SP_DocumentDetail.

    Child insert directo (mismo patron de _alerts.insert_alert) sin re-save
    del padre, para no re-disparar hooks del doctype.
    """
    frappe = _resolve_frappe(frappe)

    now = entry["entry_date"] or _now_str()
    try:
        last = frappe.db.sql(
            """
            SELECT COALESCE(MAX(idx), 0)
            FROM `tabqp_SP_TimelineEntry`
            WHERE parent = %s AND parenttype = %s
            """,
            (parent_name, DOCUMENT_DETAIL),
        ) or [[0]]
        idx = int((last[0][0] or 0)) + 1
    except (TypeError, ValueError, IndexError):
        idx = 1
    row_name = frappe.generate_hash(length=10)

    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_TimelineEntry`
        (name, parent, parentfield, parenttype, idx, entry_type, message,
         old_state, new_state, entry_by, entry_date, creation, modified,
         modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row_name,
            parent_name,
            "timeline",
            DOCUMENT_DETAIL,
            idx,
            entry["type"],
            entry["message"],
            entry.get("old_state") or None,
            entry.get("new_state") or None,
            entry["entry_by"],
            now,
            now,
            now,
            "Administrator",
            "Administrator",
        ),
    )


def _insert_read_row(parent_name, user, now, frappe=None):
    """Inserta la marca de lectura (qp_SP_TimelineRead) como child directo."""
    frappe = _resolve_frappe(frappe)
    try:
        last = frappe.db.sql(
            """
            SELECT COALESCE(MAX(idx), 0)
            FROM `tabqp_SP_TimelineRead`
            WHERE parent = %s AND parenttype = %s
            """,
            (parent_name, DOCUMENT_DETAIL),
        ) or [[0]]
        idx = int((last[0][0] or 0)) + 1
    except (TypeError, ValueError, IndexError):
        idx = 1
    row_name = frappe.generate_hash(length=10)

    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_TimelineRead`
        (name, parent, parentfield, parenttype, idx, user, last_read,
         creation, modified, modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row_name,
            parent_name,
            "timeline_read",
            DOCUMENT_DETAIL,
            idx,
            user,
            now,
            now,
            now,
            "Administrator",
            "Administrator",
        ),
    )


class RealTimelineAdapter(object):
    """Timeline de qp_SP_DocumentDetail sobre frappe (modo real)."""

    def __init__(self, frappe_module=None):
        self._frappe = _resolve_frappe(frappe_module)

    def get(self, doc_name):
        frappe = self._frappe

        timeline_rows = frappe.get_all(
            TIMELINE_ENTRY,
            filters={"parent": doc_name, "parenttype": DOCUMENT_DETAIL},
            fields=[
                "entry_type", "message", "old_state", "new_state",
                "entry_by", "entry_date",
            ],
        )

        timeline = [
            {
                "type": row.get("entry_type"),
                "message": row.get("message") or "",
                "old_state": row.get("old_state") or None,
                "new_state": row.get("new_state") or None,
                "entry_by": row.get("entry_by") or "",
                "entry_date": row.get("entry_date") or "",
            }
            for row in timeline_rows
        ]
        return order_desc(timeline)

    def add_comment(self, doc_name, comment, user=None, now=None):
        entry = build_comment_entry(
            comment, _user_name(user, self._frappe), _now_str(now)
        )
        _insert_row(doc_name, entry, self._frappe)
        return entry

    def set_state(self, doc_name, new_state, extra_fields=None, user=None, now=None,
                  old_state=None):
        frappe = self._frappe

        if old_state is None:
            old_state = frappe.db.get_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta")
        if (old_state or "") == (new_state or ""):
            return None
        frappe.db.set_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta", new_state)
        if extra_fields:
            frappe.db.set_value(DOCUMENT_DETAIL, doc_name, extra_fields)
        entry = build_state_entry(
            old_state, new_state, _user_name(user, frappe), _now_str(now)
        )
        _insert_row(doc_name, entry, frappe)
        return entry

    def record_creation(self, doc_name, user=None, now=None):
        frappe = self._frappe

        state = frappe.db.get_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta")
        entry = build_creation_entry(state, _user_name(user, frappe), _now_str(now))
        _insert_row(doc_name, entry, frappe)
        return entry

    # ------------------------------------------------------------------
    # Conversacion y lectura
    # ------------------------------------------------------------------
    def get_comments(self, doc_name):
        frappe = self._frappe

        rows = frappe.get_all(
            TIMELINE_ENTRY,
            filters={
                "parent": doc_name,
                "parenttype": DOCUMENT_DETAIL,
                "entry_type": ENTRY_COMMENT,
            },
            fields=[
                "entry_type", "message", "old_state", "new_state",
                "entry_by", "entry_date",
            ],
        )
        comments = [
            {
                "type": row.get("entry_type"),
                "message": row.get("message") or "",
                "old_state": row.get("old_state") or None,
                "new_state": row.get("new_state") or None,
                "entry_by": row.get("entry_by") or "",
                "entry_date": row.get("entry_date") or "",
            }
            for row in rows
        ]
        return order_desc(comments)

    def _session_user(self):
        return getattr(self._frappe.session, "user", "Administrator")

    def _last_read_for(self, doc_name, user):
        rows = self._frappe.get_all(
            TIMELINE_READ,
            filters={
                "parent": doc_name,
                "parenttype": DOCUMENT_DETAIL,
                "user": user,
            },
            fields=["last_read"],
        )
        return rows[0].get("last_read") if rows else None

    def mark_read(self, doc_name, user=None, now=None):
        frappe = self._frappe
        user = user or self._session_user()
        now = _now_str(now)

        existing = frappe.get_all(
            TIMELINE_READ,
            filters={
                "parent": doc_name,
                "parenttype": DOCUMENT_DETAIL,
                "user": user,
            },
            fields=["name"],
            limit=1,
        )
        if existing:
            frappe.db.set_value(TIMELINE_READ, existing[0]["name"], "last_read", now)
        else:
            _insert_read_row(doc_name, user, now, frappe)

    def unread_count(self, doc_name, user=None):
        frappe = self._frappe
        user = user or self._session_user()
        last_read = self._last_read_for(doc_name, user)
        own = _user_name(user, frappe)

        comments = frappe.get_all(
            TIMELINE_ENTRY,
            filters={
                "parent": doc_name,
                "parenttype": DOCUMENT_DETAIL,
                "entry_type": ENTRY_COMMENT,
            },
            fields=["entry_by", "entry_date"],
        )
        count = 0
        for comment in comments:
            if (comment.get("entry_by") or "") == own:
                continue
            entry_date = str(comment.get("entry_date") or "")
            if last_read and entry_date and entry_date <= str(last_read):
                continue
            count += 1
        return count

    def has_unread(self, doc_name, user=None):
        return self.unread_count(doc_name, user=user) > 0