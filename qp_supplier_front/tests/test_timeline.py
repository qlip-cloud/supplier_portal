# -*- coding: utf-8 -*-
"""
test_timeline.py
=================
Pruebas del timeline de facturas documenteme en modo real: adaptador
infrastructure/adapters/timeline_adapter.py (RealTimelineAdapter) y el hook
before_save de resources/documenteme/timeline.py.

frappe se mockea por completo (sin base); el adapter importa frappe de forma
lazy, por lo que basta con parchear sys.modules.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_timeline.py -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.uses_cases.documenteme.timeline import (
    build_comment_entry,
    build_state_entry,
)


def _sql_side_effect(query, params=None):
    if str(query).lstrip().upper().startswith("SELECT"):
        return [[0]]
    return None


def _make_frappe():
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    def get_fullname(user):
        return "Admin Name" if user == "admin@example.com" else user

    utils.get_fullname = get_fullname
    frappe.utils = utils
    frappe.session = MagicMock()
    frappe.session.user = "admin@example.com"
    frappe.db = MagicMock()
    frappe.db.get_value.return_value = "E"
    frappe.db.sql.side_effect = _sql_side_effect
    frappe.get_all = MagicMock(return_value=[])
    frappe.generate_hash = MagicMock(return_value="HASH001")

    def _whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    frappe.whitelist = _whitelist
    frappe.response = {}
    return frappe, utils


class TestRealTimelineAdapter(unittest.TestCase):

    def setUp(self):
        self.frappe, self.utils = _make_frappe()
        self.patcher = patch.dict(
            sys.modules,
            {"frappe": self.frappe, "frappe.utils": self.utils},
        )
        self.patcher.start()
        from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
            RealTimelineAdapter,
        )
        self.adapter = RealTimelineAdapter()

    def tearDown(self):
        self.patcher.stop()

    def test_add_comment_inserta_fila(self):
        entry = self.adapter.add_comment("D1", "Revisar monto elevado")
        self.assertEqual(entry, build_comment_entry(
            "Revisar monto elevado", "Admin Name", entry["entry_date"]))
        self.assertTrue(self.frappe.db.sql.called)

    def test_set_state_cuando_cambia(self):
        entry = self.adapter.set_state("D1", "V")
        self.assertEqual(entry["type"], "estado")
        self.assertEqual(entry["old_state"], "E")
        self.assertEqual(entry["new_state"], "V")
        self.assertEqual(entry["entry_by"], "Admin Name")
        self.frappe.db.set_value.assert_called_once()

    def test_set_state_mismo_estado_no_op(self):
        self.frappe.db.get_value.return_value = "V"
        self.assertIsNone(self.adapter.set_state("D1", "V"))
        self.frappe.db.set_value.assert_not_called()

    def test_set_state_con_old_state_explicito(self):
        self.frappe.db.get_value.return_value = "BCC"
        entry = self.adapter.set_state("D1", "A", old_state="E")
        self.assertEqual(entry["old_state"], "E")
        self.frappe.db.get_value.assert_not_called()

    def test_set_state_extra_fields(self):
        self.adapter.set_state("D1", "A", extra_fields={"qp_is_event_completed": 1})
        calls = self.frappe.db.set_value.call_args_list
        self.assertEqual(calls[0][0],
                         ("qp_SP_DocumentDetail", "D1", "nvfac_esta", "A"))
        self.assertEqual(calls[1][0],
                         ("qp_SP_DocumentDetail", "D1", {"qp_is_event_completed": 1}))

    def test_record_creation(self):
        entry = self.adapter.record_creation("D1")
        self.assertEqual(entry["type"], "creacion")
        self.assertEqual(entry["new_state"], "E")

    def test_get_solo_filas_timeline(self):
        self.frappe.get_all.return_value = []
        self.assertEqual(self.adapter.get("D1"), [])

        self.frappe.get_all.side_effect = [
            [{"entry_type": "comentario", "message": "c1", "old_state": None,
              "new_state": None, "entry_by": "Admin Name",
              "entry_date": "2026-09-01 09:00:00"}],
        ]
        entries = self.adapter.get("D1")
        self.assertEqual([e["type"] for e in entries], ["comentario"])
        self.assertEqual(self.frappe.get_all.call_count, 2)


def _make_doc(frappe, new=False, old_state="E", new_state="V", doctype="qp_SP_DocumentDetail"):
    doc = MagicMock()
    doc.doctype = doctype
    doc.get.return_value = new_state
    if new:
        doc.get_doc_before_save.return_value = None
    else:
        before = MagicMock()
        before.get.return_value = old_state
        doc.get_doc_before_save.return_value = before
    return doc


class TestBeforeSaveHook(unittest.TestCase):

    def setUp(self):
        self.frappe, self.utils = _make_frappe()
        self.patcher = patch.dict(
            sys.modules,
            {"frappe": self.frappe, "frappe.utils": self.utils},
        )
        self.patcher.start()
        from qp_supplier_front.resources.documenteme import timeline as tl_module
        self.tl_module = tl_module

    def tearDown(self):
        self.patcher.stop()

    def test_documento_nuevo_registra_creacion(self):
        doc = _make_doc(self.frappe, new=True, new_state="E")
        self.tl_module.on_document_before_save(doc, None)
        doc.append.assert_called_once()
        args, kwargs = doc.append.call_args
        self.assertEqual(args[0], "timeline")
        entry = args[1]
        self.assertEqual(entry["type"], "creacion")
        self.assertEqual(entry["new_state"], "E")

    def test_cambio_estado_registra_estado(self):
        doc = _make_doc(self.frappe, new=False, old_state="E", new_state="V")
        self.tl_module.on_document_before_save(doc, None)
        args, kwargs = doc.append.call_args
        self.assertEqual(args[0], "timeline")
        self.assertEqual(args[1], build_state_entry("E", "V", "Admin Name", args[1]["entry_date"]))

    def test_sin_cambio_estado_no_agrega(self):
        doc = _make_doc(self.frappe, new=False, old_state="V", new_state="V")
        self.tl_module.on_document_before_save(doc, None)
        doc.append.assert_not_called()

    def test_otros_doctypes_ignorados(self):
        doc = _make_doc(self.frappe, new=True, doctype="User")
        self.tl_module.on_document_before_save(doc, None)
        doc.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()