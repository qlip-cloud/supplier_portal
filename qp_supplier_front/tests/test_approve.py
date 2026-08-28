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
    collect_registrable_violations,
    get_error_message,
    get_registrable_blockers,
    get_registrable_warnings,
    homologate_lines,
    is_definitive,
    is_error_response,
    is_invoice_already_registered,
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
        "nvfac_conv": "2",
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


def _bank(total):
    """Construye un callback de banco de recepciones desde un total escalar."""
    if total is None:
        return lambda purchase_order: []
    return lambda purchase_order: [{
        "name": "R1",
        "amount": total,
        "date": "2026-01-01",
        "qp_invoice": None,
    }]


class TestIsDefinitive(unittest.TestCase):

    def test_estados_definitivos(self):
        for status in FINAL_STATES:
            self.assertTrue(is_definitive(status))

    def test_estados_no_definitivos(self):
        for status in ("E", "V", "T", None, ""):
            self.assertFalse(is_definitive(status))


class TestIsInvoiceAlreadyRegistered(unittest.TestCase):

    def test_detecta_mensaje_de_duplicado_con_numero(self):
        self.assertTrue(is_invoice_already_registered(
            "Error Ya existe la factura de compra SETT0501165 para este proveedor"
        ))

    def test_detecta_mensaje_de_duplicado_sin_numero(self):
        self.assertTrue(is_invoice_already_registered(
            "Error Ya existe la factura para este proveedor."
        ))

    def test_detecta_case_insensitive(self):
        self.assertTrue(is_invoice_already_registered("YA EXISTE LA FACTURA X"))

    def test_no_detecta_otros_errores(self):
        self.assertFalse(is_invoice_already_registered("BC caido"))
        self.assertFalse(is_invoice_already_registered("timeout"))

    def test_no_detecta_valores_no_string(self):
        self.assertFalse(is_invoice_already_registered(None))
        self.assertFalse(is_invoice_already_registered(0))
        self.assertFalse(is_invoice_already_registered({}))


class TestValidateRegistrable(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=50000):
        return _bank(total)

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

    def test_estado_no_analisis_no_registrable(self):
        for status in ("BCC", "PA", "PR"):
            doc = _doc(nvfac_esta=status)
            ok, error = validate_registrable(
                doc, self._po_exists(), self._receipts_total()
            )
            self.assertFalse(ok)
            self.assertIn("no registrable", error)

    def test_contado_con_estado_no_analisis_no_registrable(self):
        doc = _doc(nvfac_conv="1", nvfac_esta="BCC")
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertFalse(ok)
        self.assertIn("no registrable", error)

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
        self.assertIn("combinación", error)

    def test_montos_superan_factura(self):
        ok, _ = validate_registrable(
            _doc(), self._po_exists(), self._receipts_total(60000)
        )
        self.assertFalse(ok)


class TestValidateRegistrables(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=50000):
        return _bank(total)

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
        return [_line()], ""

    def _get_headquarter(self, purchase_order):
        return "HQ01"

    def _multi_lines(self, purchase_order):
        return [
            _line(name="LINE1", item_code="M000455", idx=2),
            _line(name="LINE2", item_code="M000456", idx=5),
        ], ""

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
        payload = build_payload([_doc()], lambda po: ([], ""), self._get_headquarter)
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
            return [_line()], ""

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

    def test_duplicado_detiene_reintento_con_callback(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001"), _doc(name="DOC2", nvfac_nume="FAC002")]
        results = [
            {"doc_number": "", "error": "Error Ya existe la factura de compra SETT0501165 para este proveedor"},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        calls["duplicate_marked"] = []

        def mark_duplicate_registered_fn(doc, error, now):
            calls["duplicate_marked"].append((doc.get("nvfac_nume"), error, now))

        kwargs["mark_duplicate_registered_fn"] = mark_duplicate_registered_fn

        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["nvfac_nume"], "FAC002")
        self.assertEqual(len(result["errors"]), 1)
        err = result["errors"][0]
        self.assertEqual(err["nvfac_nume"], "FAC001")
        self.assertEqual(err["name"], "DOC1")
        self.assertTrue(err["duplicate"])
        self.assertIn("Ya existe la factura", err["error"])

        self.assertEqual(calls["persisted"], [("FAC002", "BC1002")])
        self.assertEqual(calls["marked"], ["FAC002"])
        self.assertEqual(calls["marked_error"], [])
        self.assertEqual(len(calls["duplicate_marked"]), 1)
        self.assertEqual(calls["duplicate_marked"][0][0], "FAC001")
        self.assertEqual(calls["duplicate_marked"][0][1], results[0]["error"])
        self.assertEqual(calls["duplicate_marked"][0][2], self.NOW)
        self.assertEqual(calls["commits"], 1)

    def test_duplicado_sin_callback_mantiene_comportamiento(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        results = [
            {"doc_number": "", "error": "Error Ya existe la factura para este proveedor."},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["errors"]), 1)
        self.assertNotIn("duplicate", result["errors"][0])
        self.assertEqual(calls["marked"], [])
        self.assertEqual(calls["marked_error"], [
            ("FAC001", "Error Ya existe la factura para este proveedor."),
        ])

    def test_error_no_duplicado_no_llama_callback(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        results = [{"doc_number": "", "error": "BC caido"}]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        calls["duplicate_marked"] = []

        def mark_duplicate_registered_fn(doc, error, now):
            calls["duplicate_marked"].append(doc.get("nvfac_nume"))

        kwargs["mark_duplicate_registered_fn"] = mark_duplicate_registered_fn

        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertNotIn("duplicate", result["errors"][0])
        self.assertEqual(calls["duplicate_marked"], [])
        self.assertEqual(calls["marked_error"], [("FAC001", "BC caido")])

    def test_duplicado_callback_con_excepcion_vuelve_a_error(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        results = [
            {"doc_number": "", "error": "Error Ya existe la factura de compra SETT0501165 para este proveedor"},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )

        def mark_duplicate_registered_fn(doc, error, now):
            raise Exception("alerta fallo")

        kwargs["mark_duplicate_registered_fn"] = mark_duplicate_registered_fn

        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertNotIn("duplicate", result["errors"][0])
        self.assertIn("Ya existe la factura", result["errors"][0]["error"])
        self.assertEqual(calls["marked_error"], [
            ("FAC001", "Error Ya existe la factura de compra SETT0501165 para este proveedor"),
        ])

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


class TestApproveDocumentsReceiptBank(unittest.TestCase):
    """Ruta batch-aware (receipt_bank_fn): asignacion por banco + consumo."""

    NOW = "2026-08-12 10:00:00"

    def _callbacks(self, docs, response_obj, status, invoice_results=None,
                   bank_by_po=None):
        calls = {
            "sent": [],
            "persisted": [],
            "marked": [],
            "marked_error": [],
            "consumed": [],
            "commits": 0,
        }

        def get_docs_fn(doc_names):
            return [d for d in docs if d.get("name") in doc_names]

        def get_lines_fn(doc):
            return [_line()], ""

        def get_headquarter_fn(purchase_order):
            return "HQ01"

        def po_exists_fn(purchase_order):
            return bool(purchase_order)

        def receipt_bank_fn(purchase_order):
            return (bank_by_po or {}).get(purchase_order, [])

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
            return response_obj, status

        def parse_doc_numbers_fn(resp):
            return invoice_results or []

        def persist_invoice_fn(doc, doc_number, now):
            calls["persisted"].append((doc.get("nvfac_nume"), doc_number))

        def mark_registered_fn(doc, doc_number):
            calls["marked"].append(doc.get("nvfac_nume"))

        def mark_error_fn(doc, error):
            calls["marked_error"].append((doc.get("nvfac_nume"), error))

        def consume_receipts_fn(doc, receipt_names):
            calls["consumed"].append((doc.get("nvfac_nume"), list(receipt_names)))

        def commit_fn():
            calls["commits"] += 1

        return calls, {
            "get_docs_fn": get_docs_fn,
            "get_lines_fn": get_lines_fn,
            "get_headquarter_fn": get_headquarter_fn,
            "po_exists_fn": po_exists_fn,
            "receipt_bank_fn": receipt_bank_fn,
            "consume_receipts_fn": consume_receipts_fn,
            "send_request_fn": send_request_fn,
            "parse_doc_numbers_fn": parse_doc_numbers_fn,
            "persist_invoice_fn": persist_invoice_fn,
            "mark_registered_fn": mark_registered_fn,
            "mark_error_fn": mark_error_fn,
            "commit_fn": commit_fn,
        }

    def test_valida_por_banco_y_consume_solo_al_persistir(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde="OC111", nvfac_totp=50000),
            _doc(name="DOC2", nvfac_nume="FAC002", nvfac_orde="OC222", nvfac_totp=30000),
        ]
        results = [
            {"doc_number": "BC1001", "error": ""},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs,
            {"Result": 0, "invoices": results},
            200,
            invoice_results=results,
            bank_by_po={
                "OC111": [{"name": "R1", "amount": 50000, "date": "2026-01-01", "qp_invoice": None}],
                "OC222": [{"name": "R2", "amount": 30000, "date": "2026-01-01", "qp_invoice": None}],
            },
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 2)
        self.assertEqual(result["errors"], [])
        self.assertEqual(calls["persisted"], [("FAC001", "BC1001"), ("FAC002", "BC1002")])
        self.assertEqual(calls["consumed"], [
            ("FAC001", ["R1"]),
            ("FAC002", ["R2"]),
        ])
        self.assertEqual(calls["commits"], 1)

    def test_factura_sin_combinacion_exacta_no_se_envia_ni_consume(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_totp=50000)
        calls, kwargs = self._callbacks(
            [doc],
            {"Result": 0},
            200,
            bank_by_po={
                "45238": [{"name": "R1", "amount": 40000, "date": "2026-01-01", "qp_invoice": None}],
            },
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("combinación", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])
        self.assertEqual(calls["consumed"], [])

    def test_dos_facturas_misma_oc_en_batched_se_sirven_del_resto(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001", nvfac_totp=50000),
            _doc(name="DOC2", nvfac_nume="FAC002", nvfac_totp=30000),
        ]
        bank = [
            {"name": "R1", "amount": 50000, "date": "2026-01-01", "qp_invoice": None},
            {"name": "R2", "amount": 30000, "date": "2026-01-02", "qp_invoice": None},
        ]
        results = [
            {"doc_number": "BC1001", "error": ""},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs,
            {"Result": 0, "invoices": results},
            200,
            invoice_results=results,
            bank_by_po={"45238": bank},
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 2)
        self.assertEqual(len(result["errors"]), 0)
        consumed = dict(calls["consumed"])
        self.assertEqual(consumed["FAC001"], ["R1"])
        self.assertEqual(consumed["FAC002"], ["R2"])

    def test_duplicado_no_consume_recepciones(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde="OC111", nvfac_totp=50000),
            _doc(name="DOC2", nvfac_nume="FAC002", nvfac_orde="OC222", nvfac_totp=30000),
        ]
        results = [
            {"doc_number": "", "error": "Error Ya existe la factura para este proveedor."},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs,
            {"Result": 0, "invoices": results},
            200,
            invoice_results=results,
            bank_by_po={
                "OC111": [{"name": "R1", "amount": 50000, "date": "2026-01-01", "qp_invoice": None}],
                "OC222": [{"name": "R2", "amount": 30000, "date": "2026-01-01", "qp_invoice": None}],
            },
        )
        calls["duplicate_marked"] = []

        def mark_duplicate_registered_fn(doc, error, now):
            calls["duplicate_marked"].append(doc.get("nvfac_nume"))

        kwargs["mark_duplicate_registered_fn"] = mark_duplicate_registered_fn

        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["nvfac_nume"], "FAC002")
        self.assertEqual(calls["consumed"], [("FAC002", ["R2"])])
        self.assertEqual(calls["duplicate_marked"], ["FAC001"])

    def test_contado_en_ruta_batch_aware_se_aprueba_sin_banco(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_conv="1", nvfac_orde=None)
        calls, kwargs = self._callbacks(
            [doc],
            {"Result": 0, "invoices": [{"doc_number": "BC1001", "error": ""}]},
            200,
            invoice_results=[{"doc_number": "BC1001", "error": ""}],
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(calls["consumed"], [])

    def test_force_no_consume_aunque_exista_match(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_totp=50000)
        calls, kwargs = self._callbacks(
            [doc],
            {"Result": 0, "invoices": [{"doc_number": "BC1001", "error": ""}]},
            200,
            invoice_results=[{"doc_number": "BC1001", "error": ""}],
            bank_by_po={
                "45238": [{"name": "R1", "amount": 50000, "date": "2026-01-01", "qp_invoice": None}],
            },
        )
        result = approve_documents(["DOC1"], now=self.NOW, force=True, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(calls["persisted"], [("FAC001", "BC1001")])
        self.assertEqual(calls["consumed"], [])

    def test_sin_orden_de_compra_en_ruta_batch_aware(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde=None)
        calls, kwargs = self._callbacks([doc], {"Result": 0}, 200)
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertIn("orden de compra", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])

    def test_orden_de_compra_inexistente_en_ruta_batch_aware(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde="OC_FALTA")
        calls, kwargs = self._callbacks([doc], {"Result": 0}, 200)

        def po_exists_fn(purchase_order):
            return False

        kwargs["po_exists_fn"] = po_exists_fn

        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertIn("no existe", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])

    def test_banco_vacio_en_ruta_batch_aware(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_totp=50000)
        calls, kwargs = self._callbacks([doc], {"Result": 0}, 200, bank_by_po={"45238": []})
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertIn("recepciones", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])

    def test_bloqueo_duro_en_ruta_batch_aware(self):
        doc = _doc(name="DOC1", nvfac_nume="FAC001", nvfac_esta="A")
        calls, kwargs = self._callbacks([doc], {"Result": 0}, 200)
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertIn("definitivo", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])


class TestValidateCash(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=None):
        return _bank(total)

    def test_contado_se_aprueba_sin_oc_ni_recibos(self):
        doc = _doc(nvfac_conv="1", nvfac_orde=None)
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_contado_definitivo_no_aprueba(self):
        doc = _doc(nvfac_conv="1", nvfac_esta="A")
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertFalse(ok)
        self.assertIn("definitivo", error)

    def test_credito_sigue_exigiendo_recepciones(self):
        doc = _doc(nvfac_conv="2")
        ok, error = validate_registrable(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertFalse(ok)
        self.assertIn("recepciones", error)

    def test_sin_conv_se_trata_como_credito(self):
        doc = _doc(nvfac_conv=None)
        ok, _ = validate_registrable(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertFalse(ok)


class TestHomologateLines(unittest.TestCase):

    def test_mapea_codigos_al_codigo_bc(self):
        detail_lines = [
            {"nvpro_codi": "A-0", "nvuni_desc": "UN", "nvdet_tcan": 2, "nvdet_valo": 100},
            {"nvpro_codi": "A-2", "nvuni_desc": "UN", "nvdet_tcan": 3, "nvdet_valo": 200},
        ]
        homologation_map = {"A-0": "B-1", "A-2": "B-1"}
        lines, missing = homologate_lines(detail_lines, homologation_map)
        self.assertEqual(missing, [])
        self.assertEqual(lines[0]["item_code"], "B-1")
        self.assertEqual(lines[0]["qty"], 2)
        self.assertEqual(lines[0]["rate"], 100)
        self.assertEqual(lines[0]["receiving_no"], "")
        self.assertEqual(lines[0]["order_no"], "")
        self.assertEqual(lines[1]["item_code"], "B-1")

    def test_varios_codigos_proveedor_a_un_mismo_bc(self):
        detail_lines = [
            {"nvpro_codi": "A-0", "nvdet_tcan": 1, "nvdet_valo": 10},
            {"nvpro_codi": "A-2", "nvdet_tcan": 1, "nvdet_valo": 10},
            {"nvpro_codi": "A-4", "nvdet_tcan": 1, "nvdet_valo": 10},
        ]
        homologation_map = {"A-0": "B-1", "A-2": "B-1", "A-4": "B-1"}
        lines, missing = homologate_lines(detail_lines, homologation_map)
        self.assertEqual(missing, [])
        self.assertEqual([line["item_code"] for line in lines], ["B-1", "B-1", "B-1"])

    def test_codigo_sin_homologacion_se_reporta(self):
        detail_lines = [
            {"nvpro_codi": "A-0", "nvdet_tcan": 1, "nvdet_valo": 10},
            {"nvpro_codi": "X-99", "nvdet_tcan": 1, "nvdet_valo": 10},
        ]
        homologation_map = {"A-0": "B-1"}
        lines, missing = homologate_lines(detail_lines, homologation_map)
        self.assertEqual(missing, ["X-99"])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["item_code"], "B-1")

    def test_linea_sin_codigo_proveedor_se_omite(self):
        detail_lines = [
            {"nvpro_codi": "", "nvdet_tcan": 1, "nvdet_valo": 10},
        ]
        lines, missing = homologate_lines(detail_lines, {})
        self.assertEqual(lines, [])
        self.assertEqual(missing, [])


class TestApproveDocumentsHomologation(unittest.TestCase):

    NOW = "2026-08-12 10:00:00"

    def _callbacks(self, docs, response_obj, status, invoice_results=None,
                   line_error=""):
        calls = {
            "sent": [],
            "persisted": [],
            "marked": [],
            "marked_error": [],
            "commits": 0,
        }

        def get_docs_fn(doc_names):
            return [d for d in docs if d.get("name") in doc_names]

        def get_lines_fn(doc):
            if line_error:
                return [], line_error
            return [_line()], ""

        def get_headquarter_fn(purchase_order):
            return "HQ01"

        def po_exists_fn(purchase_order):
            return bool(purchase_order)

        def receipts_total_fn(purchase_order):
            return 50000

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
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

    def test_error_de_linea_no_envia_esa_factura(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_conv="1")]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": []}, 200,
            line_error="Faltan homologaciones de producto: X-99",
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(calls["sent"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("X-99", result["errors"][0]["error"])
        self.assertEqual(calls["marked_error"], [
            ("FAC001", "Faltan homologaciones de producto: X-99"),
        ])

    def test_contado_sin_recibo_con_lineas_ok(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_conv="1", nvfac_orde=None)]
        results = [{"doc_number": "BC1001", "error": ""}]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(len(result["approved"]), 1)
        endpoint_code, payload = calls["sent"][0]
        self.assertEqual(endpoint_code, "create_purchase_order")
        self.assertEqual(calls["persisted"], [("FAC001", "BC1001")])
        self.assertEqual(calls["marked"], ["FAC001"])


class TestGetRegistrableBlockers(unittest.TestCase):

    def test_estado_definitivo_bloquea(self):
        for status in FINAL_STATES:
            self.assertTrue(get_registrable_blockers(_doc(nvfac_esta=status)))

    def test_estado_no_analisis_bloquea(self):
        for status in ("BCC", "PA", "PR"):
            self.assertTrue(get_registrable_blockers(_doc(nvfac_esta=status)))

    def test_estado_de_analisis_no_bloquea(self):
        for status in ("E", "V", "T"):
            self.assertEqual(
                get_registrable_blockers(_doc(nvfac_esta=status)), ""
            )


class TestGetRegistrableWarnings(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=50000):
        return _bank(total)

    def test_sin_violaciones(self):
        warnings = get_registrable_warnings(
            _doc(), self._po_exists(), self._receipts_total()
        )
        self.assertEqual(warnings, [])

    def test_contado_nunca_tiene_advertencias(self):
        doc = _doc(nvfac_conv="1", nvfac_orde=None)
        warnings = get_registrable_warnings(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertEqual(warnings, [])

    def test_sin_orden_de_compra(self):
        warnings = get_registrable_warnings(
            _doc(nvfac_orde=None), self._po_exists(), self._receipts_total()
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("orden de compra", warnings[0])

    def test_orden_de_compra_inexistente(self):
        warnings = get_registrable_warnings(
            _doc(), self._po_exists(False), self._receipts_total()
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("no existe", warnings[0])

    def test_sin_recepciones(self):
        warnings = get_registrable_warnings(
            _doc(), self._po_exists(), self._receipts_total(None)
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("recepciones", warnings[0])

    def test_montos_no_coinciden(self):
        warnings = get_registrable_warnings(
            _doc(), self._po_exists(), self._receipts_total(40000)
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("combinación", warnings[0])

    def test_acumula_todas_las_violaciones(self):
        doc = _doc(nvfac_orde=None, nvfac_totp=None)
        docs = [doc]
        warnings = get_registrable_warnings(
            doc, self._po_exists(), self._receipts_total(None)
        )
        self.assertEqual(len(warnings), 1)


class TestCollectRegistrableViolations(unittest.TestCase):

    def _po_exists(self, exists=True):
        return lambda purchase_order: exists

    def _receipts_total(self, total=50000):
        return _bank(total)

    def test_devuelve_violaciones_por_factura(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde=None),
            _doc(name="DOC2", nvfac_nume="FAC002"),
        ]
        violations = collect_registrable_violations(
            docs, self._po_exists(), self._receipts_total(50000)
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["nvfac_nume"], "FAC001")
        self.assertEqual(len(violations[0]["violations"]), 1)

    def test_excluye_facturas_hard_blocked(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde=None, nvfac_esta="BCC"),
            _doc(name="DOC2", nvfac_nume="FAC002", nvfac_esta="A", nvfac_orde=None),
            _doc(name="DOC3", nvfac_nume="FAC003", nvfac_orde=None),
        ]
        violations = collect_registrable_violations(
            docs, self._po_exists(), self._receipts_total()
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["nvfac_nume"], "FAC003")

    def test_cumple_regla_no_devuelve_nada(self):
        violations = collect_registrable_violations(
            [_doc()], self._po_exists(), self._receipts_total()
        )
        self.assertEqual(violations, [])


class TestApproveDocumentsForce(unittest.TestCase):

    NOW = "2026-08-12 10:00:00"

    def _callbacks(self, docs, response_obj, status, invoice_results=None):
        calls = {
            "sent": [],
            "persisted": [],
            "marked": [],
            "marked_error": [],
            "commits": 0,
        }

        def get_docs_fn(doc_names):
            return [d for d in docs if d.get("name") in doc_names]

        def get_lines_fn(doc):
            return [_line()], ""

        def get_headquarter_fn(purchase_order):
            return "HQ01"

        def po_exists_fn(purchase_order):
            return bool(purchase_order)

        def receipts_total_fn(purchase_order):
            return 50000

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
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

    def _results(self, docs):
        return [
            {"doc_number": "BC{}".format(i + 1), "error": ""}
            for i in range(len(docs))
        ]

    def test_sin_force_no_aprueba_sin_oc(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde=None)]
        results = self._results(docs)
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(calls["sent"], [])

    def test_force_aprueba_sin_oc(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde=None)]
        results = self._results(docs)
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs, force=True)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["nvfac_nume"], "FAC001")
        self.assertEqual(len(calls["sent"]), 1)
        self.assertEqual(calls["sent"][0][0], "create_purchase_order")
        self.assertEqual(calls["persisted"], [("FAC001", "BC1")])
        self.assertEqual(calls["marked"], ["FAC001"])

    def test_force_aprueba_sin_recepciones(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        results = self._results(docs)
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs, force=True)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(result["errors"]), 0)
        self.assertEqual(calls["persisted"], [("FAC001", "BC1")])

    def test_force_aprueba_montos_no_coinciden(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001")]
        results = self._results(docs)
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs, force=True)

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(result["errors"]), 0)
        self.assertEqual(calls["persisted"], [("FAC001", "BC1")])

    def test_force_aun_bloquea_estado_definitivo(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_esta="A")]
        results = self._results(docs)
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs, force=True)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("definitivo", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])

    def test_force_aun_bloquea_estado_no_analisis(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_esta="BCC")]
        results = self._results(docs)
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs, force=True)

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("no registrable", result["errors"][0]["error"])
        self.assertEqual(calls["sent"], [])

    def test_force_lote_mixto(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001", nvfac_orde=None),
            _doc(name="DOC2", nvfac_nume="FAC002", nvfac_esta="BCC", nvfac_orde=None),
            _doc(name="DOC3", nvfac_nume="FAC003"),
        ]
        results = self._results(docs[:2])
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1", "DOC2", "DOC3"], now=self.NOW,
                                   **kwargs, force=True)

        self.assertEqual([a["nvfac_nume"] for a in result["approved"]],
                         ["FAC001", "FAC003"])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["nvfac_nume"], "FAC002")


if __name__ == "__main__":
    unittest.main()
