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


class TestBuildSendDouble(unittest.TestCase):

    def test_respuesta_exitosa_con_prefijo_sim(self):
        send = simulation.build_send_double()
        response, status = send(
            endpoint_code="create_purchase_order",
            payload=[{"NoFacturaProveedor": "FAC-001"}],
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 0)
        self.assertEqual(response["invoices"][0]["doc_number"], "SIMFAC-001")
        self.assertEqual(response["invoices"][0]["error"], "")

    def test_doc_numbers_personalizados_por_orden(self):
        send = simulation.build_send_double(invoice_numbers=["BC001", "BC002"])
        response, _ = send(
            endpoint_code="x",
            payload=[{"NoFacturaProveedor": "F1"}, {"NoFacturaProveedor": "F2"}],
        )
        self.assertEqual(response["invoices"][0]["doc_number"], "BC001")
        self.assertEqual(response["invoices"][1]["doc_number"], "BC002")

    def test_fail_numbers_error_por_factura(self):
        send = simulation.build_send_double(fail_numbers=["FAC-001"])
        response, _ = send(
            endpoint_code="x",
            payload=[{"NoFacturaProveedor": "FAC-001"}, {"NoFacturaProveedor": "FAC-002"}],
        )
        self.assertEqual(response["invoices"][0]["doc_number"], "")
        self.assertTrue(response["invoices"][0]["error"])
        self.assertEqual(response["invoices"][1]["doc_number"], "SIMFAC-002")

    def test_fail_all_error_global(self):
        send = simulation.build_send_double(fail_all=True)
        response, _ = send(
            endpoint_code="x", payload=[{"NoFacturaProveedor": "FAC-001"}]
        )
        self.assertEqual(response["Result"], 1)
        self.assertEqual(response["invoices"], [])

    def test_simulate_duplicate_segunda_llamada(self):
        send = simulation.build_send_double(simulate_duplicate=True)
        first, _ = send(endpoint_code="x", payload=[{"NoFacturaProveedor": "F1"}])
        self.assertEqual(first["Result"], 0)
        second, _ = send(endpoint_code="x", payload=[{"NoFacturaProveedor": "F1"}])
        self.assertEqual(second["Result"], 1)
        self.assertEqual(second["Description"], "Duplicado")

    def test_sin_payload_retorna_vacio(self):
        send = simulation.build_send_double()
        response, _ = send()
        self.assertEqual(response["invoices"], [])


class TestBuildHttpDouble(unittest.TestCase):

    def test_respuesta_exitosa(self):
        http = simulation.build_http_double()
        response, status = http({"Nvfac_cont": "1"}, "http://x", {}, "POST")
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 0)

    def test_fail_all(self):
        http = simulation.build_http_double(fail_all=True)
        response, status = http({"Nvfac_cont": "1"}, "http://x", {}, "POST")
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 1)

    def test_fail_cont_numbers(self):
        http = simulation.build_http_double(fail_cont_numbers=["22222"])
        response, _ = http({"Nvfac_cont": "22222"}, "http://x", {}, "POST")
        self.assertEqual(response["Result"], 1)
        ok, _ = http({"Nvfac_cont": "33333"}, "http://x", {}, "POST")
        self.assertEqual(ok["Result"], 0)

    def test_already_applied_siempre(self):
        http = simulation.build_http_double(already_applied=True)
        response, _ = http({"Nveve_dian": "031"}, "http://x", {}, "POST")
        self.assertEqual(response["Result"], 1)
        self.assertIn("ya fue emitido", response["Description"])

    def test_already_applied_once_primer_intento(self):
        http = simulation.build_http_double(already_applied_once=True)
        payload = {"Nveve_dian": "031", "Nvfac_cont": "1"}
        first, _ = http(payload, "http://x", {}, "POST")
        self.assertEqual(first["Result"], 1)
        self.assertIn("ya fue emitido", first["Description"])
        second, _ = http(payload, "http://x", {}, "POST")
        self.assertEqual(second["Result"], 0)

    def test_payload_con_cont_no_rompe(self):
        http = simulation.build_http_double()
        response, _ = http(None, "http://x", {}, "POST")
        self.assertEqual(response["Result"], 0)


class TestBuildInboundSyncDouble(unittest.TestCase):

    def _headers(self):
        return [{"Nvfac_nume": "FAC-001", "Nvfac_ueve": ""}]

    def _details(self):
        return {"FAC-001": {"Document": {"Nvfac_nume": "FAC-001"}}}

    def test_fase_listado_devuelve_cabeceras(self):
        send = simulation.build_inbound_sync_double(
            headers=self._headers(), details=self._details()
        )
        response, status = send(
            endpoint_code="documenteme_list_documents",
            param="nvemp_nnit=999999999&nvfac_esta=T",
            is_query_param=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["Result"], 0)
        self.assertEqual(len(response["LDocuments"]), 1)

    def test_fase_detalle_coincide_por_nvfac_nume(self):
        send = simulation.build_inbound_sync_double(
            headers=self._headers(), details=self._details()
        )
        response, _ = send(
            endpoint_code="documenteme_detail_document",
            param="nvemp_nnit=999999999&nvfac_esta=E&nvfac_nume=FAC-001",
            is_query_param=True,
        )
        self.assertEqual(response["Result"], 0)
        self.assertEqual(response["Document"]["Nvfac_nume"], "FAC-001")

    def test_fail_all_error_en_listado(self):
        send = simulation.build_inbound_sync_double(fail_all=True)
        response, _ = send(
            endpoint_code="documenteme_list_documents",
            param="nvemp_nnit=999999999",
            is_query_param=True,
        )
        self.assertEqual(response["Result"], 1)

    def test_fail_numes_error_en_detalle(self):
        send = simulation.build_inbound_sync_double(
            headers=self._headers(),
            details=self._details(),
            fail_numes=["FAC-001"],
        )
        response, _ = send(
            endpoint_code="documenteme_detail_document",
            param="nvfac_nume=FAC-001",
            is_query_param=True,
        )
        self.assertEqual(response["Result"], 1)

    def test_detalle_sin_fixture_retorna_error(self):
        send = simulation.build_inbound_sync_double(
            headers=self._headers(), details={}
        )
        response, _ = send(
            endpoint_code="documenteme_detail_document",
            param="nvfac_nume=FAC-001",
            is_query_param=True,
        )
        self.assertEqual(response["Result"], 1)
        self.assertIn("No hay fixture", response["Description"])

    def test_endpoint_desconocido_retorna_error(self):
        send = simulation.build_inbound_sync_double()
        response, _ = send(endpoint_code="otro", param="", is_query_param=True)
        self.assertEqual(response["Result"], 1)

    def test_sin_fixtures_responde_vacio(self):
        send = simulation.build_inbound_sync_double()
        response, _ = send(
            endpoint_code="documenteme_list_documents",
            param="nvemp_nnit=999999999",
            is_query_param=True,
        )
        self.assertEqual(response["LDocuments"], [])


class TestLoadFixtures(unittest.TestCase):

    def test_carga_fixtures_del_archivo(self):
        fixtures = simulation.load_fixtures()
        self.assertIn("headers", fixtures)
        self.assertIn("details", fixtures)
        self.assertIsInstance(fixtures["headers"], list)
        self.assertIsInstance(fixtures["details"], dict)

    def test_archivo_inexistente_devuelve_vacio(self):
        fixtures = simulation.load_fixtures(path="/tmp/no-existe-fixtures.json")
        self.assertEqual(fixtures, {"headers": [], "details": {}})


class TestBuildConfirmationId(unittest.TestCase):

    def test_deterministico(self):
        self.assertEqual(
            simulation.build_confirmation_id("SIMFAC-1"), "SIMCONF-SIMFAC-1"
        )


class TestRunSimulatedConfirmation(unittest.TestCase):

    def test_confirma_cada_doc_aprobado(self):
        calls = []

        def process_confirmation_fn(doc_number, confirmation_id):
            calls.append((doc_number, confirmation_id))
            return {"ok": True, "doc": {"name": doc_number}}

        results = simulation.run_simulated_confirmation(
            [
                {"name": "D1", "nvfac_nume": "FAC-1", "doc_number": "SIMFAC-1"},
                {"name": "D2", "nvfac_nume": "FAC-2", "doc_number": "SIMFAC-2"},
            ],
            process_confirmation_fn=process_confirmation_fn,
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(calls[0][0], "SIMFAC-1")
        self.assertEqual(calls[0][1], "SIMCONF-SIMFAC-1")
        self.assertTrue(results[0]["ok"])

    def test_omite_items_sin_doc_number(self):
        def process_confirmation_fn(doc_number, confirmation_id):
            return {"ok": True}

        results = simulation.run_simulated_confirmation(
            [{"name": "D1", "nvfac_nume": "FAC-1"}],
            process_confirmation_fn=process_confirmation_fn,
        )
        self.assertEqual(results, [])

    def test_propaga_resultado_no_ok(self):
        def process_confirmation_fn(doc_number, confirmation_id):
            return {"ok": False, "errors": ["No encontrada"]}

        results = simulation.run_simulated_confirmation(
            [{"doc_number": "SIMFAC-1"}],
            process_confirmation_fn=process_confirmation_fn,
        )
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["confirmation_id"], "SIMCONF-SIMFAC-1")


if __name__ == "__main__":
    unittest.main()