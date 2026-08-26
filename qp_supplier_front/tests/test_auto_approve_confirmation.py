# -*- coding: utf-8 -*-
"""
test_auto_approve_confirmation.py
=================================
Pruebas unitarias para resources/documenteme/auto_approve_confirmation.py.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_approve_confirmation.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()

from qp_supplier_front.resources.documenteme import auto_approve_confirmation as mod  # noqa: E402
from qp_supplier_front.resources.documenteme.auto_approve_confirmation import (  # noqa: E402, F401
    APPROVAL_EVENT_ORDER,
    get_approval_resume_index,
    build_approval_events,
    is_sequence_successful,
)


class MockLogRow(object):

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockDoc(object):

    def __init__(self, name="FAC001", nvfac_esta="BCC", event_logs=None):
        self._saved = False
        self.name = name
        self.nvfac_esta = nvfac_esta
        self.nvfac_ueve = None
        self.qp_is_event_completed = 0
        self.nvpro_ndoc = "900123456"
        self.nvfac_cont = 1
        self.event_logs = event_logs or []

    def append(self, table_name):
        row = MockLogRow()
        self.event_logs.append(row)
        return row

    def save(self):
        self._saved = True

    def get(self, key, default=None):
        value = getattr(self, key, default)
        if key == "event_logs" and value is None:
            value = []
        return value


def _make_doc(name="FAC001", nvfac_esta="BCC", event_logs=None):
    return MockDoc(name=name, nvfac_esta=nvfac_esta, event_logs=event_logs)


class TestGetApprovalResumeIndex(unittest.TestCase):

    def _logs(self, *items):
        return [dict(item) for item in items]

    def test_sin_logs_reanuda_0(self):
        self.assertEqual(get_approval_resume_index([]), 0)

    def test_un_error_en_032_reanuda_desde_030(self):
        logs = self._logs(
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 500},
        )
        self.assertEqual(get_approval_resume_index(logs), 0)

    def test_error_en_033_reanuda_desde_030(self):
        logs = self._logs(
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 200},
            {"event_code": "033", "status": 500},
        )
        self.assertEqual(get_approval_resume_index(logs), 0)

    def test_todo_exitoso_reanuda_0(self):
        logs = self._logs(
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 200},
            {"event_code": "033", "status": 200},
        )
        self.assertEqual(get_approval_resume_index(logs), 0)

    def test_ignora_eventos_fuera_de_secuencia(self):
        logs = self._logs({"event_code": "999", "status": 500})
        self.assertEqual(get_approval_resume_index(logs), 0)


class TestBuildApprovalEvents(unittest.TestCase):

    def test_secuencia_completa(self):
        doc = _make_doc()
        events = build_approval_events(doc, "890900123", 0, base_state="BCC")
        codes = [e["event_code"] for e in events]
        self.assertEqual(codes, ["030", "032", "033"])

    def test_resume_desde_032(self):
        doc = _make_doc()
        events = build_approval_events(doc, "890900123", 1, base_state="BCC")
        codes = [e["event_code"] for e in events]
        self.assertEqual(codes, ["032", "033"])

    def test_resume_desde_033(self):
        doc = _make_doc()
        events = build_approval_events(doc, "890900123", 2, base_state="BCC")
        codes = [e["event_code"] for e in events]
        self.assertEqual(codes, ["033"])

    def test_payload_033_lleva_nvfac_esta_aprobado(self):
        events = build_approval_events(
            _make_doc(), "890900123", 2, base_state="BCC"
        )
        payload = events[0]["payload"]
        self.assertEqual(payload["Nveve_dian"], "033")
        self.assertEqual(payload["Nvfac_esta"], "A")
        self.assertEqual(payload["Nvint_desc"], "Factura aprobada")

    def test_030_y_032_llevan_estado_documenteme_e(self):
        events = build_approval_events(
            _make_doc(), "890900123", 0, base_state="BCC"
        )
        by_code = {e["event_code"]: e["payload"]["Nvfac_esta"] for e in events}
        self.assertEqual(by_code["030"], "E")
        self.assertEqual(by_code["032"], "E")
        self.assertEqual(by_code["033"], "A")

    def test_todos_los_eventos_llevan_descripcion_factura_aprobada(self):
        events = build_approval_events(
            _make_doc(), "890900123", 0, base_state="BCC"
        )
        for event in events:
            self.assertEqual(
                event["payload"]["Nvint_desc"], "Factura aprobada"
            )


class TestIsSequenceSuccessful(unittest.TestCase):

    def test_exito_ultimo_033(self):
        sent = [{"event_code": "033", "response": {"Result": 0}, "status": 200}]
        self.assertTrue(is_sequence_successful(sent))

    def test_falla_ultimo_033(self):
        sent = [{"event_code": "033", "response": {"Result": 1}, "status": 200}]
        self.assertFalse(is_sequence_successful(sent))

    def test_falla_si_ultimo_no_es_033(self):
        sent = [{"event_code": "032", "response": {"Result": 0}, "status": 200}]
        self.assertFalse(is_sequence_successful(sent))

    def test_falla_si_no_hay_eventos(self):
        self.assertFalse(is_sequence_successful([]))


class TestApproveBatchJob(unittest.TestCase):

    def test_marca_aprobado_en_flujo_exitoso(self):
        doc = _make_doc()

        with patch.object(mod, "get_approval_config", return_value={
            "max_attempts": 2,
            "retry_interval": 0,
            "event_delay": 0,
        }), \
             patch.object(mod, "get_company_tax_id", return_value="890900123"), \
             patch.object(mod, "get_event_endpoint", return_value=(
                 "http://x", {"k": "v"}, "POST")), \
             patch.object(mod, "_send_event", return_value=(
                 {"Result": 0}, 200)), \
             patch.object(mod, "insert_alert") as insert_alert, \
             patch.object(mod, "resolve_open_alerts") as resolve:
            mod.frappe.get_doc = lambda doctype, name: doc
            result = mod._approve_one(
                doc,
                {"max_attempts": 2, "retry_interval": 0, "event_delay": 0},
                "890900123",
                "http://x",
                {"k": "v"},
                "POST",
            )

        self.assertTrue(result["approved"])
        self.assertEqual(doc.nvfac_esta, "A")
        self.assertEqual(doc.nvfac_ueve, "033")
        self.assertEqual(doc.qp_is_event_completed, 1)
        resolve.assert_called_once_with(doc.name)
        insert_alert.assert_not_called()

    def test_agota_intentos_y_agrega_alerta(self):
        doc = _make_doc()

        with patch.object(mod, "get_approval_config", return_value={
            "max_attempts": 2,
            "retry_interval": 0,
            "event_delay": 0,
        }), \
             patch.object(mod, "get_company_tax_id", return_value="890900123"), \
             patch.object(mod, "get_event_endpoint", return_value=(
                 "http://x", {"k": "v"}, "POST")), \
             patch.object(mod, "_send_event", return_value=(
                 {"Result": 1}, 200)), \
             patch.object(mod, "insert_alert") as insert_alert:
            mod.frappe.get_doc = lambda doctype, name: doc
            result = mod._approve_one(
                doc,
                {"max_attempts": 2, "retry_interval": 0, "event_delay": 0},
                "890900123",
                "http://x",
                {"k": "v"},
                "POST",
            )

        self.assertFalse(result["approved"])
        self.assertEqual(result["error"], "Maximo de intentos alcanzado")
        insert_alert.assert_called_once()
        self.assertEqual(doc.nvfac_esta, "BCC")


if __name__ == "__main__":
    unittest.main()
