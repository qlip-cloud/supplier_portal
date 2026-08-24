# -*- coding: utf-8 -*-
"""
test_event_notifier.py
======================
Pruebas unitarias para uses_cases/documenteme/event_notifier.py
y uses_cases/documenteme/reject.py

Completamente aisladas de Frappe y de la base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_event_notifier.py -v
"""
import copy
import unittest
from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    send_event_sequence,
    _get_last_event_idx,
    _get_nvfac_esta,
    DOCUMENTEME_EVENT_STATES,
    EVENT_ORDER,
)
from qp_supplier_front.uses_cases.documenteme.reject import reject_document


SUCCESS_RESPONSE = {"Result": 0, "Description": "Estado de documento actualizado.", "Document": None, "lAttached": None}


class MockLogRow(object):
    pass


class MockDoc(object):

    def __init__(self, nvfac_nume="SETT4000051", nvfac_esta="E", nvpro_ndoc="900123456",
                 nvfac_cont=1, event_logs=None):
        self._saved = False
        self.name = nvfac_nume
        self.nvfac_nume = nvfac_nume
        self.nvfac_esta = nvfac_esta
        self.nvpro_ndoc = nvpro_ndoc
        self.nvfac_cont = nvfac_cont
        self.nvfac_ueve = None
        self.qp_motive = None
        self.qp_is_event_completed = 0
        self.event_logs = event_logs or []

    def append(self, table_name):
        row = MockLogRow()
        self.event_logs.append(row)
        return row

    def save(self):
        self._saved = True

    def get(self, key, default=None):
        return getattr(self, key, default)


def _make_doc(nvfac_nume="SETT4000051", nvfac_esta="E", nvpro_ndoc="900123456",
              nvfac_cont=1, event_logs=None):
    return MockDoc(
        nvfac_nume=nvfac_nume,
        nvfac_esta=nvfac_esta,
        nvpro_ndoc=nvpro_ndoc,
        nvfac_cont=nvfac_cont,
        event_logs=event_logs,
    )


def _make_send_request_success():
    captured = []

    def fn(endpoint_code=None, payload=None):
        captured.append({"endpoint_code": endpoint_code, "payload": copy.deepcopy(payload)})
        return (SUCCESS_RESPONSE, 200)

    return fn, captured


def _make_send_request_error():
    captured = []

    def fn(endpoint_code=None, payload=None):
        captured.append({"endpoint_code": endpoint_code, "payload": copy.deepcopy(payload)})
        return ({"Result": 1, "Description": "Error simulado"}, 200)

    return fn, captured


def _make_send_request_http_error():
    captured = []

    def fn(endpoint_code=None, payload=None):
        captured.append({"endpoint_code": endpoint_code, "payload": copy.deepcopy(payload)})
        return ({"Error": "Timeout"}, 500)

    return fn, captured


def _make_send_request_exception():
    captured = []

    def fn(endpoint_code=None, payload=None):
        captured.append({"endpoint_code": endpoint_code, "payload": copy.deepcopy(payload)})
        raise Exception("Connection refused")

    return fn, captured


def _commit():
    captured = []
    captured.append(True)
    return captured


def _get_company_tax_id():
    return "890900123"


def _now_fn():
    return "2026-07-08 12:00:00"


# ===========================================================================
# _get_last_event_idx
# ===========================================================================
class TestGetLastEventIdx(unittest.TestCase):

    def test_no_logs_returns_minus_one(self):
        self.assertEqual(_get_last_event_idx([]), -1)

    def test_none_logs_returns_minus_one(self):
        self.assertEqual(_get_last_event_idx(None), -1)

    def test_only_failed_logs_returns_minus_one(self):
        logs = [{"event_code": "030", "status": 500}]
        self.assertEqual(_get_last_event_idx(logs), -1)

    def test_first_event_successful_returns_0(self):
        logs = [{"event_code": "030", "status": 200}]
        self.assertEqual(_get_last_event_idx(logs), 0)

    def test_first_two_successful_returns_1(self):
        logs = [
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 200},
        ]
        self.assertEqual(_get_last_event_idx(logs), 1)

    def test_all_successful_returns_2(self):
        logs = [
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 200},
            {"event_code": "031", "status": 201},
        ]
        self.assertEqual(_get_last_event_idx(logs), 2)

    def test_ignores_unknown_event_codes(self):
        logs = [
            {"event_code": "030", "status": 200},
            {"event_code": "999", "status": 200},
        ]
        self.assertEqual(_get_last_event_idx(logs), 0)


# ============================================================================
# _get_nvfac_esta — estados validos de documenteme por evento
# ============================================================================
class TestDocumentemeEventStates(unittest.TestCase):

    def test_mapeo_estados_documenteme(self):
        self.assertEqual(DOCUMENTEME_EVENT_STATES, {
            "030": "E",
            "032": "E",
            "031": "R",
            "033": "A",
        })

    def test_030_y_032_siempre_e(self):
        doc = _make_doc(nvfac_esta="PA")
        self.assertEqual(_get_nvfac_esta(doc, "030", {}, base_state="BCC"), "E")
        self.assertEqual(_get_nvfac_esta(doc, "032", {}, base_state="BCC"), "E")

    def test_031_siempre_r(self):
        doc = _make_doc(nvfac_esta="PR")
        self.assertEqual(_get_nvfac_esta(doc, "031", {}, base_state=None), "R")

    def test_033_siempre_a(self):
        doc = _make_doc(nvfac_esta="BCC")
        self.assertEqual(_get_nvfac_esta(doc, "033", {}, base_state="BCC"), "A")

    def test_evento_desconocido_cae_a_override(self):
        doc = _make_doc(nvfac_esta="V")
        event_config = {"999": {"nvfac_esta": "X"}}
        self.assertEqual(_get_nvfac_esta(doc, "999", event_config, None), "X")

    def test_evento_desconocido_cae_a_base_state(self):
        doc = _make_doc(nvfac_esta="V")
        self.assertEqual(_get_nvfac_esta(doc, "999", {}, "BCC"), "BCC")


# ============================================================================
# send_event_sequence — exito
# ============================================================================
class TestSendEventSequenceHappyPath(unittest.TestCase):

    def test_sends_all_three_events_in_order(self):
        doc = _make_doc()
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        self.assertEqual(len(captured), 3)
        codes = [c["payload"]["Nveve_dian"] for c in captured]
        self.assertEqual(codes, ["030", "032", "031"])

    def test_payload_has_correct_fields_for_030(self):
        doc = _make_doc()
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        payload = captured[0]["payload"]
        self.assertEqual(payload["Nvemp_nnit"], "890900123")
        self.assertEqual(payload["Nvpro_ndoc"], "900123456")
        self.assertEqual(payload["Nvfac_cont"], 1)
        self.assertEqual(payload["Nvfac_esta"], "E")
        self.assertEqual(payload["Nveve_dian"], "030")
        self.assertIn("Nvint_desc", payload)

    def test_031_uses_overridden_nvfac_esta(self):
        doc = _make_doc()
        event_config = {"031": {"nvfac_esta": "R"}}
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, event_config, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        payload_031 = captured[2]["payload"]
        self.assertEqual(payload_031["Nvfac_esta"], "R")

    def test_030_032_use_doc_nvfac_esta(self):
        doc = _make_doc(nvfac_esta="E")
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        self.assertEqual(captured[0]["payload"]["Nvfac_esta"], "E")
        self.assertEqual(captured[1]["payload"]["Nvfac_esta"], "E")

    def test_logs_are_appended_to_doc(self):
        doc = _make_doc()
        send_fn, _ = _make_send_request_success()

        self.assertEqual(len(doc.event_logs), 0)

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        self.assertEqual(len(doc.event_logs), 3)
        for log in doc.event_logs:
            self.assertEqual(log.status, 200)
            self.assertTrue(hasattr(log, "event_code"))
            self.assertTrue(hasattr(log, "payload"))
            self.assertTrue(hasattr(log, "response"))
            self.assertTrue(hasattr(log, "attempt_date"))

    def test_required_nvfac_esta_validation_passes(self):
        doc = _make_doc(nvfac_esta="E")
        send_fn, _ = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

    def test_required_nvfac_esta_validation_fails(self):
        doc = _make_doc(nvfac_esta="A")
        send_fn, _ = _make_send_request_success()

        with self.assertRaises(Exception) as ctx:
            send_event_sequence(
                doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
                required_nvfac_esta="E",
            )

        self.assertIn("debe tener estado 'E'", str(ctx.exception))

    def test_doc_saved_and_committed_after_each_event(self):
        doc = _make_doc()
        commit_log = []
        send_fn, _ = _make_send_request_success()

        def commit():
            commit_log.append(True)

        send_event_sequence(
            doc, {}, send_fn, commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        self.assertEqual(len(commit_log), 3)
        self.assertTrue(doc._saved)

    def test_endpoint_code_is_correct(self):
        doc = _make_doc()
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        for call in captured:
            self.assertEqual(call["endpoint_code"], "documenteme_event_document")


# ============================================================================
# send_event_sequence — reintentos (resume desde ultimo exitoso)
# ============================================================================
class TestSendEventSequenceResume(unittest.TestCase):

    def test_resume_from_030_when_only_030_completed(self):
        logs = [{"event_code": "030", "status": 200}]
        doc = _make_doc(event_logs=logs)
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        codes = [c["payload"]["Nveve_dian"] for c in captured]
        self.assertEqual(codes, ["032", "031"])

    def test_resume_from_032_when_030_and_032_completed(self):
        logs = [
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 200},
        ]
        doc = _make_doc(event_logs=logs)
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        codes = [c["payload"]["Nveve_dian"] for c in captured]
        self.assertEqual(codes, ["031"])

    def test_resume_none_when_all_completed(self):
        logs = [
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 200},
            {"event_code": "031", "status": 200},
        ]
        doc = _make_doc(event_logs=logs)
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        self.assertEqual(len(captured), 0)

    def test_resume_skips_failed_event_and_retries(self):
        logs = [
            {"event_code": "030", "status": 200},
            {"event_code": "032", "status": 500},
        ]
        doc = _make_doc(event_logs=logs)
        send_fn, captured = _make_send_request_success()

        send_event_sequence(
            doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            required_nvfac_esta="E",
        )

        codes = [c["payload"]["Nveve_dian"] for c in captured]
        self.assertEqual(codes, ["032", "031"])


# ============================================================================
# send_event_sequence — errores
# ============================================================================
class TestSendEventSequenceErrors(unittest.TestCase):

    def test_stops_on_result_1_and_raises(self):
        doc = _make_doc()
        send_fn, _ = _make_send_request_error()

        with self.assertRaises(Exception) as ctx:
            send_event_sequence(
                doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
                required_nvfac_esta="E",
            )

        self.assertIn("030", str(ctx.exception))

    def test_stops_on_http_500_and_raises(self):
        doc = _make_doc()
        send_fn, _ = _make_send_request_http_error()

        with self.assertRaises(Exception) as ctx:
            send_event_sequence(
                doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
                required_nvfac_esta="E",
            )

        self.assertIn("030", str(ctx.exception))

    def test_stops_on_exception_and_raises(self):
        doc = _make_doc()
        send_fn, _ = _make_send_request_exception()

        with self.assertRaises(Exception) as ctx:
            send_event_sequence(
                doc, {}, send_fn, _make_commit, _get_company_tax_id, _now_fn,
                required_nvfac_esta="E",
            )

        self.assertIn("030", str(ctx.exception))


# ============================================================================
# reject_document
# ============================================================================
class TestRejectDocument(unittest.TestCase):

    def test_full_reject_with_events(self):
        doc = _make_doc()
        send_fn, captured = _make_send_request_success()
        get_doc_fn = lambda doctype, name: doc

        result = reject_document(
            "002", "Error en el calculo del IVA", True,
            get_doc_fn, send_fn, _make_commit, _get_company_tax_id, _now_fn,
        )

        self.assertEqual(result.nvfac_esta, "R")
        self.assertEqual(result.qp_motive, "Error en el calculo del IVA")
        self.assertEqual(result.qp_is_event_completed, 1)
        self.assertEqual(result.nvfac_ueve, "031")
        self.assertTrue(result._saved)
        self.assertEqual(len(captured), 3)

    def test_reject_without_events_does_not_set_ueve(self):
        doc = _make_doc()
        send_fn, _ = _make_send_request_success()
        get_doc = lambda doctype, name: doc

        result = reject_document(
            "002T", "Rechazado por administrador", False,
            get_doc, send_fn, _make_commit, _get_company_tax_id, _now_fn,
        )

        self.assertEqual(result.nvfac_esta, "R")
        self.assertEqual(result.qp_motive, "Rechazado por administrador")
        self.assertEqual(result.qp_is_event_completed, 0)
        self.assertEqual(result.nvfac_ueve, None)
        self.assertEqual(len(doc.event_logs), 0)

    def test_reject_fails_when_state_is_not_E(self):
        doc = _make_doc(nvfac_esta="A")
        send_fn, _ = _make_send_request_success()
        get_doc = lambda doctype, name: doc

        with self.assertRaises(Exception) as ctx:
            reject_document(
                "002T", "Error en factura", True,
                get_doc, send_fn, _make_commit, _get_company_tax_id, _now_fn,
            )

        self.assertIn("debe tener estado 'E'", str(ctx.exception))


# ============================================================================
# helpers
# ============================================================================
def _make_commit():
    pass