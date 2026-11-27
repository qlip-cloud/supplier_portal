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
    build_documenteme_entry,
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
        entry.pop("name")
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

    def test_add_documenteme_entry(self):
        entry = self.adapter.add_documenteme_entry(
            "D1", code="030", previous_state="E", current_state="E"
        )
        self.assertEqual(entry["type"], "documenteme")
        self.assertEqual(entry["entry_by"], "Documenteme")
        self.assertIn("030", entry["message"])
        self.assertIn("Registrado", entry["message"])
        self.assertTrue(self.frappe.db.sql.called)

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

    def test_get_comments_expone_name_y_flag(self):
        self.frappe.get_all.return_value = [
            {"name": "TE1", "entry_type": "comentario", "message": "c1",
             "old_state": None, "new_state": None, "entry_by": "Admin Name",
             "entry_date": "2026-09-01 09:00:00", "send_to_bc": 1},
        ]
        comment = self.adapter.get_comments("D1")[0]
        self.assertEqual(comment["name"], "TE1")
        self.assertTrue(comment["send_to_bc"])

    def test_get_bc_comment(self):
        self.frappe.get_all.return_value = [{"message": "Entregar en bodega"}]
        self.assertEqual(self.adapter.get_bc_comment("D1"),
                         "Entregar en bodega")
        filters = self.frappe.get_all.call_args[1]["filters"]
        self.assertEqual(filters["send_to_bc"], 1)

    def test_get_bc_comment_vacio(self):
        self.frappe.get_all.return_value = []
        self.assertEqual(self.adapter.get_bc_comment("D1"), "")

    def test_get_bc_comment_entry_con_adjunto(self):
        self.frappe.get_all.return_value = [
            {"message": "Entregar", "attachment_file_url": "/files/a.pdf"},
        ]
        self.assertEqual(
            self.adapter.get_bc_comment_entry("D1"),
            {"message": "Entregar", "attachment_file_url": "/files/a.pdf"},
        )

    def test_get_bc_comment_entry_vacio(self):
        self.frappe.get_all.return_value = []
        self.assertEqual(
            self.adapter.get_bc_comment_entry("D1"),
            {"message": "", "attachment_file_url": ""},
        )

    def test_add_comment_con_adjunto(self):
        entry = self.adapter.add_comment(
            "D1", "", attachment_file_id="F1",
            attachment_file_url="/files/a.pdf", attachment_file_name="a.pdf",
        )
        self.assertEqual(entry["attachment_file_id"], "F1")
        self.assertEqual(entry["attachment_file_url"], "/files/a.pdf")
        self.assertEqual(entry["attachment_file_name"], "a.pdf")

    def test_set_comment_attachment_llama_set_value(self):
        self.frappe.get_all.return_value = []
        self.adapter.set_comment_attachment(
            "D1", "TE1", file_id="F1",
            file_url="/files/a.pdf", file_name="a.pdf",
        )
        self.frappe.db.set_value.assert_called_once_with(
            "qp_SP_TimelineEntry", "TE1",
            {
                "attachment_file_id": "F1",
                "attachment_file_url": "/files/a.pdf",
                "attachment_file_name": "a.pdf",
            },
        )

    def test_set_bc_comment_limpia_y_marca(self):
        self.frappe.get_all.return_value = []
        self.adapter.set_bc_comment("D1", "TE2", True)
        self.assertTrue(self.frappe.db.sql.called)
        self.frappe.db.set_value.assert_called_once_with(
            "qp_SP_TimelineEntry", "TE2", "send_to_bc", 1
        )

    def test_set_bc_comment_desmarca_no_escribe(self):
        self.frappe.get_all.return_value = []
        self.adapter.set_bc_comment("D1", "TE2", False)
        self.frappe.db.set_value.assert_not_called()


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

    def test_cambio_estado_automatico_usa_sistema(self):
        from qp_supplier_front.uses_cases.documenteme.timeline_origin import (
            ORIGIN_AUTOMATIC,
            timeline_origin,
        )

        doc = _make_doc(self.frappe, new=False, old_state="V", new_state="BCC")
        with timeline_origin(ORIGIN_AUTOMATIC):
            self.tl_module.on_document_before_save(doc, None)
        entry = doc.append.call_args[0][1]
        self.assertEqual(entry["origin"], "automatic")
        self.assertEqual(entry["entry_by"], "Sistema")

    def test_sin_cambio_estado_no_agrega(self):
        doc = _make_doc(self.frappe, new=False, old_state="V", new_state="V")
        self.tl_module.on_document_before_save(doc, None)
        doc.append.assert_not_called()

    def test_otros_doctypes_ignorados(self):
        doc = _make_doc(self.frappe, new=True, doctype="User")
        self.tl_module.on_document_before_save(doc, None)
        doc.append.assert_not_called()


class TestCanSendToBc(unittest.TestCase):

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

    def _can(self, backend, state):
        with patch.object(
            self.tl_module, "get_sync_backend", return_value=backend
        ), patch.object(self.tl_module, "_doc_state", return_value=state):
            return self.tl_module._can_send_to_bc(None, "D1")

    def test_estados_habilitados(self):
        for state in ("E", "V", "SO"):
            self.assertTrue(self._can("BC", state), state)

    def test_estados_deshabilitados(self):
        for state in ("BCC", "PA", "A", "R", "SR", "PSA", "PR"):
            self.assertFalse(self._can("BC", state), state)

    def test_backend_gp_deshabilitado(self):
        self.assertFalse(self._can("GP", "E"))


if __name__ == "__main__":
    unittest.main()

class TestUserAssignmentEntry(unittest.TestCase):

    def test_mensaje_sin_previos(self):
        from qp_supplier_front.uses_cases.documenteme.timeline import (
            user_assignment_message,
        )
        self.assertEqual(
            "Asignados: Ana, Luis.",
            user_assignment_message(["Ana", "Luis"], []),
        )

    def test_mensaje_con_previos(self):
        from qp_supplier_front.uses_cases.documenteme.timeline import (
            user_assignment_message,
        )
        self.assertEqual(
            "Asignados: Ana. Asignados previos: Pedro.",
            user_assignment_message(["Ana"], ["Pedro"]),
        )

    def test_mensaje_descarta_vacios(self):
        from qp_supplier_front.uses_cases.documenteme.timeline import (
            user_assignment_message,
        )
        self.assertEqual(
            "Asignados: Ana.",
            user_assignment_message(["Ana", ""], ["", None]),
        )


class TestAddUserAssignment(unittest.TestCase):

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

    def test_add_user_assignment_inserta_fila(self):
        entry = self.adapter.add_user_assignment(
            "D1", "Asignados: Ana.", user="admin@example.com")
        entry.pop("name")
        self.assertEqual(entry["type"], "asignacion_usuario")
        self.assertEqual(entry["message"], "Asignados: Ana.")
        self.assertEqual(entry["entry_by"], "Admin Name")
        self.assertEqual(entry["entry_date"], entry["entry_date"])
        self.assertTrue(self.frappe.db.sql.called)


class TestDocumentemeEntry(unittest.TestCase):

    def test_evento_sin_cambio_de_estado(self):
        entry = build_documenteme_entry(
            "030", "E", "E", "Documenteme", "2026-01-01 00:00:00")
        self.assertEqual(entry["type"], "documenteme")
        self.assertIn("evento 030", entry["message"])
        self.assertIn("Registrado", entry["message"])
        self.assertNotIn("Cambio de estado", entry["message"])

    def test_evento_con_cambio_de_estado(self):
        entry = build_documenteme_entry(
            "033", "E", "A", "Documenteme", "2026-01-01 00:00:00")
        self.assertIn("Aprobado", entry["message"])
        self.assertIn("Cambio de estado", entry["message"])

    def test_sin_codigo_reporta_estado(self):
        entry = build_documenteme_entry(
            "", "E", "A", "Documenteme", "2026-01-01 00:00:00")
        self.assertIn("estado Aprobado", entry["message"])
