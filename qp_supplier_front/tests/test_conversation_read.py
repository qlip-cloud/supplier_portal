# -*- coding: utf-8 -*-
"""
test_conversation_read.py
=========================
Pruebas de la conversacion (solo comentarios) y de las marcas de lectura por
usuario en el adaptador real (infrastructure/adapters/timeline_adapter.py) y
en el in-memory (simulation/timeline_memory.py).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_conversation_read -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.simulation.store import MemoryStore
from qp_supplier_front.simulation.timeline_memory import MemoryTimelineAdapter


def _sql_side_effect(query, params=None):
    if str(query).lstrip().upper().startswith("SELECT"):
        return [[0]]
    return None


def _make_frappe(comment_rows=None, read_rows=None, list_limit=None):
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def get_fullname(user):
        return "Admin Name" if user == "admin@example.com" else user

    utils.get_fullname = get_fullname
    frappe.utils = utils
    frappe.session = MagicMock()
    frappe.session.user = "admin@example.com"
    frappe.db = MagicMock()
    frappe.db.sql.side_effect = _sql_side_effect
    frappe.generate_hash = MagicMock(return_value="HASH001")

    comment_rows = comment_rows or []
    read_rows = read_rows or []

    def get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
        if doctype == "qp_SP_TimelineEntry":
            if filters and filters.get("entry_type") == "comentario":
                return comment_rows
            return comment_rows
        if doctype == "qp_SP_TimelineRead":
            return read_rows
        return []

    frappe.get_all = get_all
    return frappe, utils


def _comment_entry(name, entry_by, entry_date):
    return {
        "entry_type": "comentario",
        "message": "mensaje",
        "old_state": None,
        "new_state": None,
        "entry_by": entry_by,
        "entry_date": entry_date,
    }


class TestRealConversation(unittest.TestCase):

    def _adapter(self, comment_rows=None, read_rows=None):
        frappe, utils = _make_frappe(comment_rows, read_rows)
        patcher = patch.dict(
            sys.modules,
            {"frappe": frappe, "frappe.utils": utils},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
            RealTimelineAdapter,
        )
        return RealTimelineAdapter(frappe_module=frappe), frappe

    def test_get_comments_solo_comentarios(self):
        adapter, frappe = self._adapter(comment_rows=[
            _comment_entry("c1", "Admin Name", "2026-09-01 09:00:00"),
        ])
        comments = adapter.get_comments("D1")
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["message"], "mensaje")
        self.assertTrue(all(c["type"] == "comentario" for c in comments))

    def test_mark_read_inserta_cuando_no_existe(self):
        adapter, frappe = self._adapter(read_rows=[])
        adapter.mark_read("D1")
        insert_calls = [
            call for call in frappe.db.sql.call_args_list
            if str(call[0][0]).lstrip().upper().startswith("INSERT")
        ]
        self.assertTrue(insert_calls)
        self.assertIn("last_read", str(insert_calls[0][0][0]))

    def test_mark_read_actualiza_cuando_existe(self):
        adapter, frappe = self._adapter(read_rows=[{
            "name": "R1", "user": "admin@example.com", "last_read": "2026-09-01 08:00:00",
        }])
        adapter.mark_read("D1")
        frappe.db.set_value.assert_called_once_with(
            "qp_SP_TimelineRead", "R1", "last_read",
            frappe.db.set_value.call_args[0][3],
        )

    def test_unread_count_ignora_comentarios_propios_y_leidos(self):
        adapter, frappe = self._adapter(
            comment_rows=[
                _comment_entry("propio", "Admin Name", "2026-09-01 09:30:00"),
                _comment_entry("leido", "Otro User", "2026-09-01 08:00:00"),
                _comment_entry("nuevo", "Otro User", "2026-09-01 09:00:00"),
            ],
            read_rows=[{
                "name": "R1", "user": "admin@example.com",
                "last_read": "2026-09-01 08:30:00",
            }],
        )
        count = adapter.unread_count("D1")
        self.assertEqual(count, 1)
        self.assertTrue(adapter.has_unread("D1"))


class TestMemoryConversation(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.store.insert("qp_SP_DocumentDetail", {
            "name": "D1", "nvfac_esta": "E",
        })
        self.adapter = MemoryTimelineAdapter(self.store)

    def test_get_comments_solo_comentarios(self):
        self.adapter.add_comment("D1", "uno", user="Admin", now="2026-09-01 09:00:00")
        self.adapter.set_state("D1", "V", user="Admin", now="2026-09-01 09:10:00")
        self.adapter.add_comment("D1", "dos", user="Admin", now="2026-09-01 09:20:00")
        comments = self.adapter.get_comments("D1")
        self.assertEqual([c["message"] for c in comments], ["dos", "uno"])
        self.assertTrue(all(c["type"] == "comentario" for c in comments))

    def test_mark_read_y_unread_por_usuario(self):
        self.adapter.add_comment("D1", "a", user="Otro", now="2026-09-01 09:00:00")
        self.adapter.add_comment("D1", "b", user="Admin", now="2026-09-01 09:30:00")

        # Sin lectura previa: el comentario ajeno cuenta, el propio no.
        self.assertEqual(self.adapter.unread_count("D1", user="Admin"), 1)

        self.adapter.mark_read("D1", user="Admin", now="2026-09-01 09:05:00")
        # "b" es propio y "a" quedo antes de last_read -> 0
        self.assertEqual(self.adapter.unread_count("D1", user="Admin"), 0)
        self.assertFalse(self.adapter.has_unread("D1", user="Admin"))

    def test_mark_read_upsert_no_duplica(self):
        self.adapter.mark_read("D1", user="Admin", now="2026-09-01 09:00:00")
        self.adapter.mark_read("D1", user="Admin", now="2026-09-01 10:00:00")
        rows = self.store.query("qp_SP_TimelineRead",
                                filters={"parent": "D1", "user": "Admin"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["last_read"], "2026-09-01 10:00:00")


if __name__ == "__main__":
    unittest.main()