# -*- coding: utf-8 -*-
"""
test_event_job.py
=================
Pruebas del job de UN evento documenteme (resources/documenteme/event_job.py)
y de la maquina de estados (uses_cases/documenteme/event_retry.py).

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_event_job.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.uses_cases.documenteme import event_retry as core  # noqa: E402
from qp_supplier_front.resources.documenteme import event_job as mod  # noqa: E402

SUCCESS = {"Result": 0, "Description": "OK"}
ERROR = {"Result": 1, "Description": "Error"}
ALREADY = {
    "Result": 1,
    "Description": "El documento [X] ya cuenta con el/los evento(s) [030] "
                   "y se encuentra(n) en estado exitoso.",
}

BASE_CONFIG = {"max_attempts": 5, "retry_interval": 60, "event_delay": 60}


class FakeDoc(object):

    def __init__(self, **overrides):
        self.name = "FAC001"
        self.nvfac_esta = "PR"
        self.nvfac_conv = "2"
        self.nvpro_ndoc = "900123456"
        self.nvfac_cont = 1
        self.nvfac_ueve = None
        self.qp_is_event_completed = 0
        self.qp_reject_retry_enabled = 1
        self.qp_reject_orig_state = "E"
        self.qp_event_sequence = "R"
        self.qp_event_pending_code = "030"
        self.qp_event_next_at = None
        self.qp_event_attempts = 0
        self.event_logs = []
        self.saved = False
        for key, value in overrides.items():
            setattr(self, key, value)

    def get(self, key, default=None):
        value = getattr(self, key, default)
        return value

    def append(self, table):
        row = MagicMock()
        self.event_logs.append(row)
        return row

    def save(self):
        self.saved = True


def _run(doc, http_fn, config=None, lock_token=None):
    bundle = {
        "event_http_fn": http_fn,
        "company_tax_id_fn": lambda: "890900123",
        "event_endpoint_fn": lambda: ("http://x", {}, "POST"),
    }
    frappe_mock = MagicMock()
    frappe_mock.get_doc.return_value = doc

    def send(payload, url, headers, method):
        return http_fn(payload)

    with patch.object(mod, "frappe", frappe_mock), \
         patch.object(mod.runtime, "resolve", return_value=bundle), \
         patch.object(mod.sync_lock, "acquire",
                      return_value={"token": "t"}), \
         patch.object(mod.sync_lock, "release"), \
         patch.object(mod, "_build_payload",
                      side_effect=lambda d, c, cfg, tax, base_state=None: {
                          "Nveve_dian": c}), \
         patch.object(mod, "_append_log"), \
         patch.object(mod, "insert_alert") as insert_alert, \
         patch.object(mod, "resolve_open_alerts") as resolve, \
         patch(
             "qp_supplier_front.resources.documenteme.auto_reject.get_reject_config",
             return_value=config or BASE_CONFIG,
         ):
        result = mod.run_documenteme_event(doc.name, http_fn=send,
                                           lock_token=lock_token)
    return result, insert_alert, resolve


class TestEventRetryCore(unittest.TestCase):

    def test_sequences(self):
        self.assertEqual(core.sequence_for("A"), ("030", "032", "033"))
        self.assertEqual(core.sequence_for("R"), ("030", "032", "031"))

    def test_first_and_next(self):
        self.assertEqual(core.first_code("R"), "030")
        self.assertEqual(core.next_code("R", "030"), "032")
        self.assertEqual(core.next_code("R", "032"), "031")
        self.assertIsNone(core.next_code("R", "031"))
        self.assertEqual(core.next_code("R", "XX"), "030")

    def test_is_final(self):
        self.assertTrue(core.is_final_code("R", "031"))
        self.assertTrue(core.is_final_code("A", "033"))
        self.assertFalse(core.is_final_code("R", "032"))

    def test_intent_from_state(self):
        self.assertEqual(core.intent_from_state("PR"), "R")
        self.assertEqual(core.intent_from_state("PA"), "A")
        self.assertEqual(core.intent_from_state("BCC"), "A")

    def test_resolve_pending_code_defaults(self):
        doc = {"qp_event_pending_code": ""}
        self.assertEqual(core.resolve_pending_code(doc, "A"), "030")
        doc = {"qp_event_pending_code": "032"}
        self.assertEqual(core.resolve_pending_code(doc, "A"), "032")
        # codigo fuera de la secuencia -> primero
        doc = {"qp_event_pending_code": "031"}
        self.assertEqual(core.resolve_pending_code(doc, "A"), "030")

    def test_send_was_successful(self):
        self.assertTrue(core.send_was_successful(SUCCESS, 200))
        self.assertTrue(core.send_was_successful(ALREADY, 200))
        self.assertFalse(core.send_was_successful(ERROR, 200))
        self.assertFalse(core.send_was_successful(SUCCESS, 500))

    def test_next_attempt_count_no_reset_on_success(self):
        # Exito intermedio NO resetea el contador acumulado.
        self.assertEqual(core.next_attempt_count(3, True), 3)
        self.assertEqual(core.next_attempt_count(3, False), 4)


class TestRunEvent(unittest.TestCase):

    def test_success_non_final_avanza(self):
        doc = FakeDoc(qp_event_pending_code="030")

        def http(payload):
            return (SUCCESS, 200)

        result, insert_alert, resolve = _run(doc, http)

        self.assertFalse(result["done"])
        self.assertEqual(doc.qp_event_pending_code, "032")
        self.assertEqual(doc.nvfac_esta, "PR")
        self.assertEqual(doc.qp_event_attempts, 0)
        self.assertIsNotNone(doc.qp_event_next_at)
        insert_alert.assert_not_called()
        resolve.assert_not_called()

    def test_success_final_marca_rechazado(self):
        doc = FakeDoc(qp_event_pending_code="031")

        def http(payload):
            return (SUCCESS, 200)

        result, insert_alert, resolve = _run(doc, http)

        self.assertTrue(result["done"])
        self.assertEqual(doc.nvfac_esta, "R")
        self.assertEqual(doc.nvfac_ueve, "031")
        self.assertEqual(doc.qp_is_event_completed, 1)
        self.assertEqual(doc.qp_event_pending_code, "")
        self.assertEqual(doc.qp_event_attempts, 0)
        resolve.assert_called_once()
        insert_alert.assert_not_called()

    def test_success_final_aprobacion(self):
        doc = FakeDoc(nvfac_esta="PA", qp_event_sequence="A",
                      qp_event_pending_code="033")

        def http(payload):
            return (SUCCESS, 200)

        result, _, _ = _run(doc, http)

        self.assertTrue(result["done"])
        self.assertEqual(doc.nvfac_esta, "A")
        self.assertEqual(doc.nvfac_ueve, "033")
        self.assertEqual(doc.qp_is_event_completed, 1)

    def test_fallo_reinicia_desde_030(self):
        doc = FakeDoc(qp_event_pending_code="031")

        def http(payload):
            return (ERROR, 200)

        result, insert_alert, _ = _run(doc, http)

        self.assertFalse(result["done"])
        self.assertEqual(doc.qp_event_pending_code, "030")
        self.assertEqual(doc.qp_event_attempts, 1)
        insert_alert.assert_not_called()

    def test_fallo_agota_intentos(self):
        doc = FakeDoc(qp_event_pending_code="031", qp_event_attempts=4)

        def http(payload):
            return (ERROR, 200)

        result, insert_alert, _ = _run(doc, http)

        self.assertEqual(result["error"], "Maximo de intentos alcanzado")
        self.assertEqual(doc.qp_event_pending_code, "")
        self.assertEqual(doc.qp_event_attempts, 0)
        self.assertEqual(doc.nvfac_esta, "PR")
        self.assertIsNotNone(doc.qp_event_next_at)
        insert_alert.assert_called_once()

    def test_ya_aplicado_avanza(self):
        doc = FakeDoc(qp_event_pending_code="030")

        def http(payload):
            return (ALREADY, 200)

        result, _, _ = _run(doc, http)

        self.assertEqual(doc.qp_event_pending_code, "032")
        self.assertEqual(doc.qp_event_attempts, 0)

    def test_ya_ha_sido_rechazado_continua_y_marca_r(self):
        # El 031 responde "ya ha sido rechazado" (Result 1): debe continuar el
        # flujo y finalizar en R sin agotar intentos.
        doc = FakeDoc(qp_event_pending_code="031", qp_event_attempts=3)
        response = {
            "Result": 1,
            "Description": (
                "El documento ya ha sido rechazado el dia [09/10/2026 "
                "03:29:39 p. m.] por el usuario [Fernando.Sanchez@MENTUM.group]."
            ),
        }

        def http(payload):
            return (response, 200)

        result, insert_alert, resolve = _run(doc, http)

        self.assertTrue(result["done"])
        self.assertEqual(doc.nvfac_esta, "R")
        self.assertEqual(doc.nvfac_ueve, "031")
        self.assertEqual(doc.qp_event_attempts, 0)
        insert_alert.assert_not_called()
        resolve.assert_called_once()

    def test_kill_switch_no_envia(self):
        doc = FakeDoc(qp_reject_retry_enabled=0)
        sent = []

        def http(payload):
            sent.append(payload)
            return (SUCCESS, 200)

        result, _, _ = _run(doc, http)

        self.assertTrue(result.get("skipped"))
        self.assertEqual(sent, [])

    def test_no_vencido_se_omite(self):
        doc = FakeDoc(qp_event_next_at="2999-01-01 00:00:00")
        sent = []

        def http(payload):
            sent.append(payload)
            return (SUCCESS, 200)

        result, _, _ = _run(doc, http)

        self.assertTrue(result.get("skipped"))
        self.assertEqual(sent, [])

    def test_lock_tomado_se_omite(self):
        doc = FakeDoc()
        frappe_mock = MagicMock()
        frappe_mock.get_doc.return_value = doc
        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod.sync_lock, "acquire", return_value=None):
            result = mod.run_documenteme_event(doc.name, http_fn=lambda p: (SUCCESS, 200))
        self.assertTrue(result.get("skipped"))
        self.assertEqual(frappe_mock.get_doc.call_count, 0)


if __name__ == "__main__":
    unittest.main()
