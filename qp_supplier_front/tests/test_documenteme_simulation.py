# -*- coding: utf-8 -*-
"""
test_documenteme_simulation.py
==============================
Pruebas unitarias para el modo simulador del flujo documenteme
(resources/documenteme/simulation.py).

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_documenteme_simulation.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import simulation  # noqa: E402


class TestIsSimulationEnabled(unittest.TestCase):

    def _run(self, frappe_mock):
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            return simulation.is_simulation_enabled()

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


class TestSendPurchaseInvoiceRequest(unittest.TestCase):

    def test_respuesta_exitosa_por_factura(self):
        payload = [
            {"NoFacturaProveedor": "FAC-001"},
            {"NoFacturaProveedor": "FAC-002"},
        ]
        response, status = simulation.send_purchase_invoice_request(
            endpoint_code="create_purchase_order", payload=payload
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 0)
        self.assertEqual(len(response["invoices"]), 2)
        self.assertEqual(response["invoices"][0]["doc_number"], "SIMFAC-001")
        self.assertEqual(response["invoices"][0]["error"], "")

    def test_doc_number_simulado_cuando_no_hay_factura(self):
        response, _ = simulation.send_purchase_invoice_request(
            endpoint_code=None, payload=None
        )
        self.assertEqual(response["invoices"], [])

    def test_sin_payload_retorna_vacio(self):
        response, status = simulation.send_purchase_invoice_request()
        self.assertEqual(status, 200)
        self.assertEqual(response["invoices"], [])


class TestSendEventRequest(unittest.TestCase):

    def test_respuesta_de_exito(self):
        response, status = simulation.send_event_request(
            endpoint_code="documenteme_event_document",
            payload={"Nveve_dian": "031"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 0)

    def test_depende_de_payload_para_resultado(self):
        response, _ = simulation.send_event_request()
        self.assertEqual(response["Result"], 0)


class TestHttpEvent(unittest.TestCase):

    def test_misma_firma_queue_raw_http(self):
        response, status = simulation.http_event(
            {"Nveve_dian": "031"}, "http://x", {}, "POST"
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 0)


class TestGetCompanyTaxId(unittest.TestCase):

    def test_nit_simulado_fijo(self):
        self.assertEqual(simulation.get_company_tax_id(), "999999999")

    def test_no_depende_de_frappe(self):
        # En simulacion no se lee Company (no importa el mock de frappe).
        self.assertEqual(simulation.get_company_tax_id(), "999999999")


class TestGetEventEndpoint(unittest.TestCase):

    def test_endpoint_simulado(self):
        url, headers, method = simulation.get_event_endpoint()
        self.assertEqual(url, "https://simulation.local/documenteme/event")
        self.assertEqual(headers, {})
        self.assertEqual(method, "POST")

    def test_sin_dependencia_qp_authorization(self):
        # No toca qp_authorization: retorna valores fijos.
        url, _, method = simulation.get_event_endpoint()
        self.assertTrue(url.startswith("https://simulation.local"))
        self.assertEqual(method, "POST")


if __name__ == "__main__":
    unittest.main()