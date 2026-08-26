# -*- coding: utf-8 -*-
"""
test_approve.py
===============
Pruebas unitarias para uses_cases/documenteme/approve.py.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_approve.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.approve import (
    FINAL_STATES,
    approve_documents,
    build_payload,
    get_error_message,
    is_definitive,
    is_error_response,
    validate_registrable,
    validate_registrables,
)


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "FAC001",
        "nvpro_ndoc": "050633410",
        "nvfac_fech": "2026-07-09 10:00:00",
        "nvfac_cufe": "",
        "nvtip_docu": "F",
        "nvfac_fpag": "",
        "nvfac_orde": "45238",
        "nvfac_rece": "R108349",
        "nvfac_totp": 50000,
        "nvfac_esta": "V",
        "nvmon_codi": "COP",
        "nvfac_stot": 50000,
        "nvfac_viva": 0,
    }
    data.update(overrides)
    return data


def _line(**overrides):
    data = {
        "name": "LINE1",
        "item_code": "M000455",
        "qty": 10,
        "rate": 5000.0,
        "idx": 1,
        "receiving_no": "R108349",
        "order_no": "45238",
    }
    data.update(overrides)
    return data


class TestIsDefinitive(unittest.TestCase):

    def test_estados_definitivos(self):
        for status in FINAL_STATES:
            self.assertTrue(is_definitive(status))

    def test_estados_no_definitivos(self):
        for status in ("E", "V", "T", None, ""):
            self.assertFalse(is_definitive(status))


class TestValidateRegistrable(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=50000):
        return lambda purchase_order: total

    def test_cumple_regla(self):
        doc = _doc()
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total()
        )
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_estado_definitivo_no_aprueba(self):
        doc = _doc(nvfac_esta="A")
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total()
        )
        self.assertFalse(ok)
        self.assertIn("definitivo", error)

    def test_rechazada_no_aprueba(self):
        doc = _doc(nvfac_esta="R")
        ok, _ = validate_registrable(
            doc, self._po_exists(), self._receipts_total()
        )
        self.assertFalse(ok)

    def test_sin_orden_de_compra(self):
        doc = _doc(nvfac_orde=None)
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total()
        )
        self.assertFalse(ok)
        self.assertIn("orden de compra", error)

    def test_orden_de_compra_inexistente(self):
        ok, error = validate_registrable(
            _doc(), self._po_exists(False), self._receipts_total()
        )
        self.assertFalse(ok)
        self.assertIn("no existe", error)

    def test_sin_recepciones(self):
        ok, error = validate_registrable(
            _doc(), self._po_exists(), self._receipts_total(None)
        )
        self.assertFalse(ok)
        self.assertIn("recepciones", error)

    def test_montos_no_coinciden(self):
        ok, error = validate_registrable(
            _doc(), self._po_exists(), self._receipts_total(40000)
        )
        self.assertFalse(ok)
        self.assertIn("no coincide", error)

    def test_montos_superan_factura(self):
        ok, _ = validate_registrable(
            _doc(), self._po_exists(), self._receipts_total(60000)
        )
        self.assertFalse(ok)


class TestValidateRegistrables(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=50000):
        return lambda purchase_order: total

    def test_separa_validos_y_errores(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001"),
            _doc(name="DOC2", nvfac_nume="FAC002", nvfac_esta="A"),
            _doc(name="DOC3", nvfac_nume="FAC003", nvfac_orde=None),
        ]
        valid, errors = validate_registrables(
            docs, self._po_exists(), self._receipts_total()
        )
        self.assertEqual([d["nvfac_nume"] for d in valid], ["FAC001"])
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]["nvfac_nume"], "FAC002")
        self.assertEqual(errors[1]["nvfac_nume"], "FAC003")


class TestBuildPayload(unittest.TestCase):

    def _get_lines(self, purchase_order):
        return [_line()]

    def _get_headquarter(self, purchase_order):
        return "HQ01"

    def _multi_lines(self, purchase_order):
        return [
            _line(name="LINE1", item_code="M000455", idx=2),
            _line(name="LINE2", item_code="M000456", idx=5),
        ]

    def test_construye_array_con_una_factura_por_doc(self):
        docs = [_doc()]
        payload = build_payload(docs, self._get_lines, self._get_headquarter)
        self.assertEqual(len(payload), 1)

        factura = payload[0]
        self.assertEqual(factura["NoFacturaProveedor"], "FAC001")
        self.assertEqual(factura["vendorNumber"], "050633410")
        self.assertEqual(factura["invoiceDate"], "2026-07-09")
        self.assertEqual(factura["postingDate"], "2026-07-09")
        self.assertEqual(factura["tipoFacturaDoc"], "Estándar")
        self.assertEqual(factura["Cufe"], "")
        self.assertIn("Almacen", factura)
        self.assertEqual(
            list(factura.keys()).index("Almacen"),
            list(factura.keys()).index("Cufe") + 1,
        )
        self.assertEqual(factura["Almacen"], "HQ01")
        self.assertEqual(factura["formaPago"], "")
        self.assertEqual(factura["dimensionSetLines"], [
            {"code": "TERCERO", "valueCode": "050633410"}
        ])

        line = factura["vendorInvoiceLine"][0]
        self.assertEqual(line["NoProducto"], "M000455")
        self.assertEqual(line["cantidad"], 10)
        self.assertEqual(line["Precio"], 5000.0)
        self.assertEqual(line["NoLineaRecepcion"], "10000")
        self.assertEqual(line["NoRecepcion"], "R108349")
        self.assertEqual(line["NoPedido"], "45238")

    def test_no_linea_recepcion_se_incrementa_por_factura(self):
        payload = build_payload([_doc()], self._multi_lines, self._get_headquarter)
        lines = payload[0]["vendorInvoiceLine"]
        self.assertEqual(
            [line["NoLineaRecepcion"] for line in lines],
            ["10000", "20000"],
        )

    def test_cufe_desde_el_doc(self):
        docs = [_doc(nvfac_cufe="CUFE123")]
        payload = build_payload(docs, self._get_lines, self._get_headquarter)
        self.assertEqual(payload[0]["Cufe"], "CUFE123")
        self.assertEqual(payload[0]["formaPago"], "")

    def test_almacen_vacio_sin_headquarter(self):
        payload = build_payload([_doc()], self._get_lines, lambda po: "")
        self.assertEqual(payload[0]["Almacen"], "")

    def test_varias_facturas_y_varias_lineas(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001"), _doc(name="DOC2", nvfac_nume="FAC002")]
        payload = build_payload(docs, self._get_lines, self._get_headquarter)
        self.assertEqual(
            [p["NoFacturaProveedor"] for p in payload],
            ["FAC001", "FAC002"],
        )

    def test_sin_lineas_de_recepcion_deja_array_vacio(self):
        payload = build_payload([_doc()], lambda po: [], self._get_headquarter)
        self.assertEqual(payload[0]["vendorInvoiceLine"], [])


class TestIsErrorResponse(unittest.TestCase):

    def test_status_no_200_es_error(self):
        self.assertTrue(is_error_response({"Result": 0}, 500))

    def test_result_1_es_error(self):
        self.assertTrue(is_error_response({"Result": 1}, 200))

    def test_result_0_ok(self):
        self.assertFalse(is_error_response({"Result": 0}, 200))

    def test_respuesta_no_dict_ok(self):
        self.assertFalse(is_error_response(None, 200))


class TestGetErrorMessage(unittest.TestCase):

    def test_prioriza_description(self):
        self.assertEqual(
            get_error_message({"Result": 1, "Description": "boom"}),
            "boom",
        )

    def test_respuesta_no_dict(self):
        self.assertEqual(get_error_message("timeout"), "timeout")


class TestApproveDocuments(unittest.TestCase):

    NOW = "2026-08-12 10:00:00"

    def _callbacks(self, docs, response_obj, status, invoice_results=None,
                   send_raises=None):
        calls = {
            "sent": [],
            "persisted": [],
            "marked": [],
            "marked_error": [],
            "commits": 0,
        }

        def get_docs_fn(doc_names):
            return [d for d in docs if d.get("name") in doc_names]

        def get_lines_fn(purchase_order):
            return [_line()]

        def get_headquarter_fn(purchase_order):
            return "HQ01"

        def po_exists_fn(purchase_order):
            return bool(purchase_order)

        def receipts_total_fn(purchase_order):
            return 50000

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
            if send_raises:
                raise send_raises
            return response_obj, status

        def parse_doc_numbers_fn(resp):
            if invoice_results is None:
                return []
            return invoice_results

        def persist_invoice_fn(doc, doc_number, now):
            calls["persisted"].append((doc.get("nvfac_nume"), doc_number))

        def mark_registered_fn(doc, doc_number):
            calls["marked"].append(doc.get("nvfac_nume"))

        def mark_error_fn(doc, error):
            calls["marked_error"].append((doc.get("nvfac_nume"), error))

        def commit_fn():
            calls["commits"] += 1

        return calls, {
            "get_docs_fn": get_docs_fn,
            "get_lines_fn": get_lines_fn,
            "get_headquarter_fn": get_headquarter_fn,
            "po_exists_fn": po_exists_fn,
            "receipts_total_fn": receipts_total_fn,
            "send_request_fn": send_request_fn,
            "parse_doc_numbers_fn": parse_doc_numbers_fn,
            "persist_invoice_fn": persist_invoice_fn,
            "mark_registered_fn": mark_registered_fn,
            "mark_error_fn": mark_error_fn,
            "commit_fn": commit_fn,
        }

    def test_aprueba_lote_exitoso_con_return_value(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001"), _doc(name="DOC2", nvfac_nume="FAC002")]
        results = [
            {"doc_number": "BC1001", "error": ""},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 2)
        self.assertEqual(result["errors"], [])

        endpoint_code, payload = calls["sent"][0]
        self.assertEqual(endpoint_code, "create_purchase_order")
        self.assertEqual(len(payload), 2)
        self.assertIn("Almacen", payload[0])
        self.assertEqual(payload[0]["Almacen"], "HQ01")

        self.assertEqual(calls["persisted"], [
            ("FAC001", "BC1001"),
            ("FAC002", "BC1002"),
        ])
        self.assertEqual(calls["marked"], ["FAC001", "FAC002"])
        self.assertEqual(calls["marked_error"], [])
        self.assertEqual(calls["commits"], 1)

    def test_docs_invalidos_no_envian(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_esta="A")]
        calls, kwargs = self._callbacks(docs, {"Result": 0}, 200)
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(calls["sent"], [])
        self.assertEqual(calls["persisted"], [])
        self.assertEqual(calls["marked_error"], [])
        self.assertEqual(calls["commits"], 0)

    def test_error_de_envio_queda_todo_en_error(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001"), _doc(name="DOC2", nvfac_nume="FAC002")]
        calls, kwargs = self._callbacks(
            docs, {"Result": 1, "Description": "BC caido"}, 200,
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 2)
        self.assertEqual(calls["persisted"], [])
        self.assertEqual(calls["marked"], [])
        self.assertEqual(calls["marked_error"], [
            ("FAC001", "BC caido"),
            ("FAC002", "BC caido"),
        ])
        self.assertEqual(calls["commits"], 0)

    def test_excepcion_en_envio_queda_todo_en_error(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        calls, kwargs = self._callbacks(
            docs, None, None, send_raises=Exception("timeout"),
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertIn("timeout", result["errors"][0]["error"])
        self.assertEqual(calls["persisted"], [])
        self.assertEqual(calls["marked_error"], [("FAC001", "timeout")])

    def test_resultado_mixto_deja_la_fallida_en_v(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001"), _doc(name="DOC2", nvfac_nume="FAC002")]
        results = [
            {"doc_number": "", "error": "Error Ya existe la factura para este proveedor."},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["nvfac_nume"], "FAC002")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["nvfac_nume"], "FAC001")
        self.assertIn("Ya existe", result["errors"][0]["error"])
        self.assertEqual(calls["persisted"], [("FAC002", "BC1002")])
        self.assertEqual(calls["marked"], ["FAC002"])
        self.assertEqual(calls["marked_error"], [
            ("FAC001", "Error Ya existe la factura para este proveedor."),
        ])
        self.assertEqual(calls["commits"], 1)

    def test_resultado_faltante_queda_en_v(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": []}, 200,
            invoice_results=[],
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("no devolvió resultado", result["errors"][0]["error"])
        self.assertEqual(calls["persisted"], [])
        self.assertEqual(len(calls["marked_error"]), 1)

    def test_error_de_persistencia_no_tumba_el_lote(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001"), _doc(name="DOC2", nvfac_nume="FAC002")]
        results = [
            {"doc_number": "BC1001", "error": ""},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )

        def persist_invoice_fn(doc, doc_number, now):
            calls["persisted"].append((doc.get("nvfac_nume"), doc_number))
            if doc.get("nvfac_nume") == "FAC001":
                raise Exception("duplicado")

        kwargs["persist_invoice_fn"] = persist_invoice_fn

        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["nvfac_nume"], "FAC002")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["nvfac_nume"], "FAC001")
        self.assertEqual(calls["marked"], ["FAC002"])
        self.assertEqual(calls["marked_error"], [("FAC001", "duplicado")])
        self.assertEqual(calls["commits"], 1)


if __name__ == "__main__":
    unittest.main()
