# -*- coding: utf-8 -*-
"""
test_documenteme_runtime.py
===========================
Pruebas unitarias del composition root del flujo documenteme
(resources/documenteme/runtime.py): unico punto que decide real vs simulado
y entrega el bundle de adaptadores sin que los orquestadores conozcan el flag.

Solo se mockea frappe puntualmente (lectura del flag); el bundle real es
verificable contra los adaptadores reales (frappe real del entorno).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_documenteme_runtime.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.resources.documenteme import runtime  # noqa: E402
from qp_supplier_front.resources.documenteme import simulation  # noqa: E402


class TestIsSimulationEnabled(unittest.TestCase):

    def _run(self, frappe_mock):
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            return runtime.is_simulation_enabled()

    def test_habilitado(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = 1
        self.assertTrue(self._run(frappe_mock))
        frappe_mock.db.get_single_value.assert_called_once_with(
            "qp_SP_MasterSetup", "documenteme_simulation"
        )

    def test_deshabilitado(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = 0
        self.assertFalse(self._run(frappe_mock))

    def test_valor_nulo_es_false(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = None
        self.assertFalse(self._run(frappe_mock))


class TestResolveRealBundle(unittest.TestCase):

    def test_modo_real_usa_adaptadores_reales(self):
        from qp_authorization.use_case.basic.authorize import send_request_status
        from qp_supplier_front.resources.documenteme import _approve_base
        from qp_supplier_front.resources.documenteme import auto_reject

        with patch.object(runtime, "is_simulation_enabled", return_value=False):
            bundle = runtime.resolve()

        self.assertIs(bundle["sync_send_fn"], send_request_status)
        self.assertIs(
            bundle["approve_send_fn"], _approve_base.send_purchase_invoice_request
        )
        self.assertIs(bundle["event_http_fn"], auto_reject.raw_http)
        self.assertIsNone(bundle["on_batch_approved_fn"])
        self.assertIn("sync_tax_id_fn", bundle)
        self.assertIn("company_tax_id_fn", bundle)
        self.assertIn("event_endpoint_fn", bundle)


class TestResolveSimulatedBundle(unittest.TestCase):

    def test_modo_simulado_usa_doubles_y_actor(self):
        with patch.object(runtime, "is_simulation_enabled", return_value=True), \
             patch.object(runtime.simulation, "load_fixtures",
                          return_value={"headers": [], "details": {}}):
            bundle = runtime.resolve()

        self.assertIs(
            bundle["approve_send_fn"], simulation.send_purchase_invoice_request
        )
        self.assertIs(bundle["event_http_fn"], simulation.http_event)
        self.assertTrue(callable(bundle["on_batch_approved_fn"]))
        self.assertEqual(bundle["company_tax_id_fn"](), "999999999")
        url, _headers, method = bundle["event_endpoint_fn"]()
        self.assertTrue(url.startswith("https://simulation.local"))
        self.assertEqual(method, "POST")

    def test_modo_simulado_usa_doble_inbound(self):
        with patch.object(runtime, "is_simulation_enabled", return_value=True), \
             patch.object(runtime.simulation, "load_fixtures",
                          return_value={"headers": [{"Nvfac_nume": "FAC-001"}],
                                        "details": {}}):
            bundle = runtime.resolve()

        response, status = bundle["sync_send_fn"](
            endpoint_code="documenteme_list_documents",
            param="nvemp_nnit=999999999",
            is_query_param=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(response["LDocuments"]), 1)
        self.assertEqual(
            bundle["sync_tax_id_fn"]("COMP-A"),
            simulation.SIMULATED_COMPANY_TAX_ID,
        )

    def test_actor_simulado_setea_simulation_confirmation(self):
        approved = [{"name": "D1", "nvfac_nume": "FAC-1", "doc_number": "SIMFAC-1"}]
        with patch.object(
            simulation, "run_simulated_confirmation",
            return_value=[{"doc_number": "SIMFAC-1", "ok": True}],
        ):
            result = {"approved": approved}
            runtime._apply_simulated_confirmation(result)
        self.assertIn("simulation_confirmation", result)


if __name__ == "__main__":
    unittest.main()