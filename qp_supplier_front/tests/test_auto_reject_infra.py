# -*- coding: utf-8 -*-
"""
test_auto_reject_infra.py
=========================
Pruebas unitarias para los callbacks de infraestructura del rechazo
automatico (resources/documenteme/auto_reject.py).

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_reject_infra.py -v
"""
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.resources.documenteme import auto_reject as infra  # noqa: E402
from qp_supplier_front.uses_cases.documenteme.auto_reject import (  # noqa: E402
    RULE_NO_PO,
    RULE_NO_RECEIPT,
)

RULE_NAME = "Sin coincidencia con Orden de Compra"


def _rule_values(rule_code=RULE_NO_PO, enabled=1):
    return (RULE_NAME, rule_code, enabled, "Rechazo automático: motivo")


def _doc(name="DOC1", nvpro_ndoc="900123456", nvfac_orde="OC111",
         nvfac_esta="E", nvfac_ueve=None):
    return {
        "name": name,
        "nvfac_nume": name,
        "nvpro_ndoc": nvpro_ndoc,
        "nvfac_orde": nvfac_orde,
        "nvfac_esta": nvfac_esta,
        "nvfac_ueve": nvfac_ueve,
        "nvfac_cont": 1,
    }


def _reject(doc="DOC1", motive="Rechazo automático: motivo", rule=RULE_NAME):
    return {"doc": doc, "motive": motive, "rule": rule}


class TestGetRule(unittest.TestCase):

    def _run(self, frappe_mock, rule_name):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_rule(rule_name)

    def test_sin_nombre_retorna_none(self):
        self.assertIsNone(self._run(MagicMock(), None))

    def test_regla_inexistente_retorna_none(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = False
        self.assertIsNone(self._run(frappe_mock, "X"))

    def test_regla_existente_devuelve_dict(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = True
        frappe_mock.db.get_value.return_value = _rule_values()
        rule = self._run(frappe_mock, RULE_NAME)
        self.assertEqual(rule["rule_code"], RULE_NO_PO)
        self.assertEqual(rule["rule_name"], RULE_NAME)
        frappe_mock.db.get_value.assert_called_once_with(
            "qp_SP_AutoRejectRule",
            RULE_NAME,
            ["rule_name", "rule_code", "enabled", "motive"],
        )


class TestGetSupplierRule(unittest.TestCase):

    def test_proveedor_con_regla(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = ["SUP1"]
        frappe_mock.db.get_value.side_effect = [RULE_NAME, _rule_values()]

        with patch.object(infra, "frappe", frappe_mock):
            rule = infra.get_supplier_rule("900123456")

        self.assertEqual(rule["rule_code"], RULE_NO_PO)
        frappe_mock.get_all.assert_called_once_with(
            "Supplier",
            filters={"tax_id": "900123456"},
            pluck="name",
            limit=1,
        )

    def test_sin_proveedor_retorna_none(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        with patch.object(infra, "frappe", frappe_mock):
            self.assertIsNone(infra.get_supplier_rule("900123456"))

    def test_sin_tax_id_retorna_none(self):
        with patch.object(infra, "frappe", MagicMock()):
            self.assertIsNone(infra.get_supplier_rule(None))


class TestGetSetupDefaultRule(unittest.TestCase):

    def test_lee_valor_del_setup(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = RULE_NAME
        frappe_mock.db.exists.return_value = True
        frappe_mock.db.get_value.return_value = _rule_values()

        with patch.object(infra, "frappe", frappe_mock):
            rule = infra.get_setup_default_rule()

        self.assertEqual(rule["rule_code"], RULE_NO_PO)
        frappe_mock.db.get_single_value.assert_called_once_with(
            "qp_SP_MasterSetup", "auto_reject"
        )


class TestResolveRule(unittest.TestCase):

    def test_regla_proveedor_gana_al_setup(self):
        supplier = {"rule_name": "A", "rule_code": RULE_NO_PO, "enabled": 1, "motive": ""}
        setup = {"rule_name": "B", "rule_code": RULE_NO_RECEIPT, "enabled": 1, "motive": ""}

        with patch.object(infra, "get_supplier_rule", return_value=supplier), \
             patch.object(infra, "get_setup_default_rule", return_value=setup):
            rule = infra.resolve_rule(_doc())

        self.assertEqual(rule["rule_code"], RULE_NO_PO)

    def test_sin_proveedor_usa_setup(self):
        setup = {"rule_name": "B", "rule_code": RULE_NO_RECEIPT, "enabled": 1, "motive": ""}

        with patch.object(infra, "get_supplier_rule", return_value=None), \
             patch.object(infra, "get_setup_default_rule", return_value=setup):
            rule = infra.resolve_rule(_doc())

        self.assertEqual(rule["rule_code"], RULE_NO_RECEIPT)


class TestPoReceiptCallbacks(unittest.TestCase):

    def test_po_exists_delega_en_db(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = "PO"
        with patch.object(infra, "frappe", frappe_mock):
            self.assertTrue(infra.po_exists("OC111"))
        frappe_mock.db.exists.assert_called_once_with("Purchase Order", "OC111")

    def test_po_exists_sin_oc(self):
        with patch.object(infra, "frappe", MagicMock()):
            self.assertFalse(infra.po_exists(None))

    def test_receipt_for_po_delega_en_get_receipt_total(self):
        with patch.object(infra, "get_receipt_total", return_value=1000):
            self.assertEqual(infra.receipt_for_po("OC111"), 1000)


class TestGetCandidates(unittest.TestCase):

    def test_filtra_solo_estado_E_y_sin_ueve(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [_doc()]

        with patch.object(infra, "frappe", frappe_mock):
            candidates = infra.get_candidates()

        self.assertEqual(len(candidates), 1)
        filters = frappe_mock.get_all.call_args[1]["filters"]
        self.assertEqual(filters["nvfac_ueve"], ["is", "not set"])
        self.assertEqual(filters["nvfac_esta"], "E")


class TestRunAutoReject(unittest.TestCase):

    def test_rechaza_y_encola_job(self):
        frappe_mock = MagicMock()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "get_candidates", return_value=[_doc()]), \
             patch.object(
                 infra, "resolve_rule",
                 return_value={"rule_name": RULE_NAME, "rule_code": RULE_NO_PO,
                               "enabled": 1, "motive": "Rechazo automático: motivo"},
             ), \
             patch.object(infra, "po_exists", return_value=False), \
             patch.object(infra, "receipt_for_po", return_value=None):
            result = infra.run_auto_reject()

        self.assertEqual(result["rejected"], ["DOC1"])
        frappe_mock.enqueue.assert_called_once_with(
            infra.REJECT_JOB_METHOD,
            rejects=[_reject()],
            queue="long",
            timeout=14400,
            job_name="auto reject documents",
        )

    def test_sin_rechazos_no_encola(self):
        frappe_mock = MagicMock()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "get_candidates", return_value=[_doc()]), \
             patch.object(infra, "resolve_rule", return_value=None):
            result = infra.run_auto_reject()

        self.assertEqual(result["rejected"], [])
        frappe_mock.enqueue.assert_not_called()

    def test_con_http_fn_ejecuta_inline(self):
        frappe_mock = MagicMock()
        executed = []

        def http_fn(payload, url, headers, method):
            executed.append(payload.get("Nveve_dian"))
            return ({"Result": 0, "Description": "OK"}, 200)

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "get_candidates", return_value=[_doc()]), \
             patch.object(
                 infra, "resolve_rule",
                 return_value={"rule_name": RULE_NAME, "rule_code": RULE_NO_PO,
                               "enabled": 1, "motive": "Rechazo automático: motivo"},
             ), \
             patch.object(infra, "po_exists", return_value=False), \
             patch.object(infra, "receipt_for_po", return_value=None), \
             patch.object(infra, "reject_batch_job") as job_mock:
            infra.run_auto_reject(http_fn=http_fn)

        job_mock.assert_called_once_with([_reject()], http_fn=http_fn)
        frappe_mock.enqueue.assert_not_called()


class MockLogRow(object):
    pass


class MockDoc(object):

    def __init__(self, name="DOC1", nvfac_esta="E"):
        self.name = name
        self.nvfac_nume = name
        self.nvfac_esta = nvfac_esta
        self.nvpro_ndoc = "900123456"
        self.nvfac_cont = 1
        self.nvfac_ueve = None
        self.qp_motive = None
        self.qp_is_event_completed = 0
        self.qp_auto_reject_rule = None
        self.event_logs = []

    def append(self, table_name):
        row = MockLogRow()
        self.event_logs.append(row)
        return row

    def save(self):
        pass

    def get(self, key, default=None):
        return getattr(self, key, default)


class TestRawHttp(unittest.TestCase):

    def test_respuesta_exitosa(self):
        resp = MagicMock()
        resp.text = json.dumps({"Result": 0})
        resp.status_code = 200
        requests_mock = MagicMock()
        requests_mock.request.return_value = resp

        with patch.object(infra, "requests", requests_mock):
            result, status = infra.raw_http(
                {"Nveve_dian": "031"}, "http://x", {}, "POST"
            )

        self.assertEqual(result, {"Result": 0})
        self.assertEqual(status, 200)

    def test_error_http_retorna_500(self):
        requests_mock = MagicMock()
        requests_mock.request.side_effect = Exception("Timeout")

        with patch.object(infra, "requests", requests_mock):
            result, status = infra.raw_http({}, "http://x", {}, "POST")

        self.assertEqual(status, 500)
        self.assertIn("errorInterno", result)


class TestDispatchHttp(unittest.TestCase):

    SUCCESS = {"Result": 0, "Description": "OK"}
    ERROR = {"Result": 1, "Description": "Error"}

    def _event(self, code):
        return {"event_code": code, "payload": {"Nveve_dian": code}}

    def test_envia_secuencia_en_orden_y_se_detiene_ante_error(self):
        tasks = [{"doc_name": "DOC1", "events": [
            self._event("030"), self._event("032"), self._event("031"),
        ]}]
        responses = {"030": self.SUCCESS, "032": self.ERROR, "031": self.SUCCESS}
        called = []

        def http_fn(payload, url, headers, method):
            code = payload["Nveve_dian"]
            called.append(code)
            return (responses[code], 200)

        with patch.object(infra, "get_event_endpoint",
                         return_value=("http://x", {}, "POST")):
            results = infra.dispatch_http(tasks, http_fn=http_fn)

        self.assertEqual(called, ["030", "032"])
        doc_name, sent = results[0]
        self.assertEqual(doc_name, "DOC1")
        self.assertEqual([s["event_code"] for s in sent], ["030", "032"])

    def test_secuencia_completa_exitosa(self):
        tasks = [{"doc_name": "DOC1", "events": [
            self._event("030"), self._event("032"), self._event("031"),
        ]}]

        def http_fn(payload, url, headers, method):
            return (self.SUCCESS, 200)

        with patch.object(infra, "get_event_endpoint",
                         return_value=("http://x", {}, "POST")):
            results = infra.dispatch_http(tasks, http_fn=http_fn)

        doc_name, sent = results[0]
        self.assertEqual([s["event_code"] for s in sent], ["030", "032", "031"])

    def test_sin_tareas_retorna_vacio(self):
        self.assertEqual(infra.dispatch_http([], http_fn=lambda *a: None), [])


class TestApplyBatchResults(unittest.TestCase):

    SUCCESS = {"Result": 0, "Description": "OK"}
    ERROR = {"Result": 1, "Description": "Error"}

    def _attempt(self, code, response, status=200):
        return {
            "event_code": code,
            "payload": {"Nveve_dian": code},
            "response": response,
            "status": status,
        }

    def test_secuencia_completa_marca_rechazada(self):
        doc = MockDoc()
        results = [("DOC1", [
            self._attempt("030", self.SUCCESS),
            self._attempt("032", self.SUCCESS),
            self._attempt("031", self.SUCCESS),
        ])]
        infra.apply_batch_results({"DOC1": {"doc": doc, "motive": "Motivo", "rule": RULE_NAME}}, results)

        self.assertEqual(doc.nvfac_esta, "R")
        self.assertEqual(doc.qp_motive, "Motivo")
        self.assertEqual(doc.qp_auto_reject_rule, RULE_NAME)
        self.assertEqual(doc.qp_is_event_completed, 1)
        self.assertEqual(doc.nvfac_ueve, "031")
        self.assertEqual(len(doc.event_logs), 3)

    def test_secuencia_incompleta_no_marca_rechazada(self):
        doc = MockDoc()
        results = [("DOC1", [
            self._attempt("030", self.SUCCESS),
            self._attempt("032", self.ERROR),
        ])]
        infra.apply_batch_results({"DOC1": {"doc": doc, "motive": "Motivo", "rule": RULE_NAME}}, results)

        self.assertEqual(doc.nvfac_esta, "E")
        self.assertEqual(doc.qp_motive, None)
        self.assertEqual(doc.qp_is_event_completed, 0)
        self.assertEqual(doc.nvfac_ueve, None)
        self.assertEqual(len(doc.event_logs), 2)


class TestRejectBatchJob(unittest.TestCase):

    SUCCESS = {"Result": 0, "Description": "OK"}

    def test_rechaza_documentos_eligibles(self):
        doc = MockDoc("DOC1", nvfac_esta="E")
        frappe_mock = MagicMock()

        def get_doc(doctype, name):
            if doctype == "qp_SP_DocumentDetail":
                return doc
            company = MagicMock()
            company.tax_id = "890900123"
            return company

        frappe_mock.get_doc.side_effect = get_doc
        frappe_mock.defaults.get_user_default.return_value = "COMP"

        def http_fn(payload, url, headers, method):
            return (self.SUCCESS, 200)

        with patch.object(infra, "frappe", frappe_mock):
            infra.reject_batch_job([_reject()], http_fn=http_fn)

        self.assertEqual(doc.nvfac_esta, "R")
        self.assertEqual(doc.qp_motive, "Rechazo automático: motivo")
        self.assertEqual(doc.qp_auto_reject_rule, RULE_NAME)
        self.assertEqual(doc.qp_is_event_completed, 1)
        self.assertEqual(doc.nvfac_ueve, "031")
        self.assertEqual(len(doc.event_logs), 3)
        frappe_mock.db.commit.assert_called()

    def test_salta_documentos_que_no_estan_en_E(self):
        doc = MockDoc("DOC1", nvfac_esta="V")
        frappe_mock = MagicMock()

        def get_doc(doctype, name):
            if doctype == "qp_SP_DocumentDetail":
                return doc
            company = MagicMock()
            company.tax_id = "890900123"
            return company

        frappe_mock.get_doc.side_effect = get_doc
        frappe_mock.defaults.get_user_default.return_value = "COMP"

        def http_fn(payload, url, headers, method):
            return (self.SUCCESS, 200)

        with patch.object(infra, "frappe", frappe_mock):
            infra.reject_batch_job([_reject()], http_fn=http_fn)

        self.assertEqual(doc.nvfac_esta, "V")
        self.assertEqual(len(doc.event_logs), 0)


if __name__ == "__main__":
    unittest.main()
