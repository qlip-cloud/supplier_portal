# -*- coding: utf-8 -*-
"""
timeline_memory.py (simulation - timeline data adapter)
========================================================
Adaptador in-memory del timeline de facturas documenteme: lee y persiste las
entradas del historial sobre el MemoryStore de la sesion (qp_SP_TimelineEntry)
y fusiona los event_logs sembrados en memoria (qp_SP_EventLog).

Implementa el contrato de domain/ports/timeline_port.py, espejo de
infrastructure/adapters/timeline_adapter.py (RealTimelineAdapter). Sin base
real: toda escritura queda en la sesion de simulacion.
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


def _now_str(now=None):
    if now:
        return now
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MemoryTimelineAdapter(object):
    """Timeline de qp_SP_DocumentDetail sobre el MemoryStore (modo simulador)."""

    def __init__(self, store):
        self._store = store

    def get(self, doc_name):
        timeline_rows = self._store.query(
            TIMELINE_ENTRY, filters={"parent": doc_name}
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
            comment, user or "Administrator", _now_str(now)
        )
        self._insert(doc_name, entry)
        return entry

    def set_state(self, doc_name, new_state, extra_fields=None, user=None, now=None,
                  old_state=None):
        if old_state is None:
            old_state = self._store.get_value(
                DOCUMENT_DETAIL, doc_name, "nvfac_esta"
            )
        if (old_state or "") == (new_state or ""):
            return None
        self._store.set_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta", new_state)
        for key, value in (extra_fields or {}).items():
            self._store.set_value(DOCUMENT_DETAIL, doc_name, key, value)
        entry = build_state_entry(
            old_state, new_state, user or "Administrator", _now_str(now)
        )
        self._insert(doc_name, entry)
        return entry

    def record_creation(self, doc_name, user=None, now=None):
        state = self._store.get_value(
            DOCUMENT_DETAIL, doc_name, "nvfac_esta"
        )
        entry = build_creation_entry(
            state, user or "Administrator", _now_str(now)
        )
        self._insert(doc_name, entry)
        return entry

    # ------------------------------------------------------------------
    # Conversacion y lectura
    # ------------------------------------------------------------------
    def get_comments(self, doc_name):
        rows = self._store.query(
            TIMELINE_ENTRY,
            filters={
                "parent": doc_name,
                "entry_type": ENTRY_COMMENT,
            },
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
        return "Administrator"

    def _last_read_for(self, doc_name, user):
        rows = self._store.query(
            TIMELINE_READ,
            filters={"parent": doc_name, "user": user},
            limit=1,
        )
        return rows[0].get("last_read") if rows else None

    def mark_read(self, doc_name, user=None, now=None):
        user = user or self._session_user()
        now = _now_str(now)
        rows = self._store.query(
            TIMELINE_READ,
            filters={"parent": doc_name, "user": user},
            limit=1,
        )
        if rows:
            self._store.set_value(
                TIMELINE_READ, rows[0]["name"], "last_read", now
            )
            return
        self._store.insert(TIMELINE_READ, {
            "parent": doc_name,
            "parenttype": DOCUMENT_DETAIL,
            "parentfield": "timeline_read",
            "user": user,
            "last_read": now,
        })

    def unread_count(self, doc_name, user=None):
        user = user or self._session_user()
        last_read = self._last_read_for(doc_name, user)
        comments = self._store.query(
            TIMELINE_ENTRY,
            filters={"parent": doc_name, "entry_type": ENTRY_COMMENT},
        )
        count = 0
        for comment in comments:
            if (comment.get("entry_by") or "") == user:
                continue
            entry_date = str(comment.get("entry_date") or "")
            if last_read and entry_date and entry_date <= str(last_read):
                continue
            count += 1
        return count

    def has_unread(self, doc_name, user=None):
        return self.unread_count(doc_name, user=user) > 0

    def _insert(self, doc_name, entry):
        self._store.insert(TIMELINE_ENTRY, {
            "parent": doc_name,
            "parenttype": DOCUMENT_DETAIL,
            "parentfield": "timeline",
            "entry_type": entry["type"],
            "message": entry["message"],
            "old_state": entry.get("old_state") or None,
            "new_state": entry.get("new_state") or None,
            "entry_by": entry["entry_by"],
            "entry_date": entry["entry_date"] or _now_str(),
        })