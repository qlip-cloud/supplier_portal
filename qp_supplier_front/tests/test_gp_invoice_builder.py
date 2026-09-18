# -*- coding: utf-8 -*-
"""
test_gp_invoice_builder.py
==========================
Pruebas del builder GP de facturas documenteme (uses_cases/documenteme/approve)
y de la normalizacion de respuesta GP (resources/documenteme/_approve_base).

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_gp_invoice_builder.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.uses_cases.documenteme.approve import (
    build_gp_invoice,
    build_gp_vendor_invoice_line,
    build_payload,
    consolidate_gp_lines,
    make_invoice_builder,
    resolve_gp_tipo,
)

from qp_supplier_front.resources.documenteme._approve_base import (
    normalize_gp_response,
    send_purchase_invoice_request_gp,
)


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "PRB002",
        "nvpro_ndoc": "ACETRAVE0001",
        "nvfac_fech": "2026-09-03 10:00:00",
        "nvfac_cufe": "",
        "nvtip_docu": "F",
        "nvfac_fpag": "",
        "nvfac_orde": "PO2075",
        "nvfac_rece": "R108349",
        "nvfac_totp": 786.60,
        "nvfac_esta": "V",
        "nvfac_conv": "2",
        "nvmon_codi": "Z-US$",
        "nvfac_stot": 786.60,
        "nvfac_viva": 0,
    }
    data.update(overrides)
    return data


def _line(**overrides):
    data = {
        "name": "LINE1",
        "item_code": "400PROC",
        "qty": 2,
        "rate": 393.30,
        "idx": 1,
        "uom": "Each",
        "receiving_no": "PO2075",
        "order_no": "PO2075",
    }
    data.update(overrides)
    return data


class TestBuildGpVendorInvoiceLine(unittest.TestCase):

    def test_mapea_campos_gp_con_defaults(self):
        line = build_gp_vendor_invoice_line(_line(), "2026-09-03T00:00:00")
        self.assertEqual(line["noProducto"], "400PROC")
        self.assertEqual(line["cantidad"], 2)
        self.assertEqual(line["precio"], 393.30)
        self.assertEqual(line["fechaRequerida"], "2026-09-03T00:00:00")
        self.assertEqual(line["fechaPrometida"], "2026-09-03T00:00:00")
        self.assertEqual(line["unidadMedida"], "Each")
        self.assertEqual(line["noLineaRecepcion"], 1)
        self.assertEqual(line["noRecepcion"], "PO2075")
        self.assertEqual(line["noPedido"], "")

    def test_unidad_medida_default_cuando_uom_vacio(self):
        line = build_gp_vendor_invoice_line(
            _line(uom=""), "2026-09-03T00:00:00"
        )
        self.assertEqual(line["unidadMedida"], "UN")

    def test_fechas_de_oc_sobreescriben_fecha_documento(self):
        line = build_gp_vendor_invoice_line(
            _line(), "2026-09-03T00:00:00",
            fecha_requerida="2026-09-01T00:00:00",
            fecha_prometida="2026-10-15T00:00:00",
        )
        self.assertEqual(line["fechaRequerida"], "2026-09-01T00:00:00")
        self.assertEqual(line["fechaPrometida"], "2026-10-15T00:00:00")


class TestBuildGpInvoice(unittest.TestCase):

    def test_forma_json_gp_con_fechas_t00(self):
        doc = _doc()
        invoice = build_gp_invoice(doc, [_line()], "HQ01")
        self.assertEqual(invoice["invoiceDate"], "2026-09-03T00:00:00")
        self.assertEqual(invoice["postingDate"], "2026-09-03T00:00:00")
        self.assertEqual(invoice["vendorNumber"], "ACETRAVE0001")
        self.assertEqual(invoice["puntofacturacion"], "")
        self.assertEqual(invoice["noFacturaProveedor"], "PRB002")
        self.assertEqual(invoice["cufe"], "")
        self.assertEqual(invoice["tipoFacturaDoc"], 2)
        self.assertEqual(invoice["formaPago"], "")
        self.assertEqual(invoice["descripcion"], "PRB002")
        self.assertEqual(invoice["valorDescuento"], 0)
        self.assertEqual(invoice["valorFlete"], 0)
        self.assertEqual(invoice["valorMiscelaneo"], 0)
        self.assertEqual(invoice["subtotal"], 786.60)
        self.assertEqual(invoice["comentario"], "")
        self.assertEqual(invoice["moneda"], "Z-US$")
        self.assertEqual(invoice["numeroPord"], "PO2075")
        self.assertEqual(invoice["dimensionSetLines"], [])
        self.assertEqual(len(invoice["vendorInvoiceLine"]), 1)
        self.assertEqual(invoice["vendorInvoiceLine"][0]["noProducto"], "400PROC")

    def test_sin_fecha_envia_fechas_vacias(self):
        invoice = build_gp_invoice(_doc(nvfac_fech=""), [_line()], "HQ01")
        self.assertEqual(invoice["invoiceDate"], "")
        self.assertEqual(invoice["postingDate"], "")

    def test_sin_lineas_envia_vendorinvoiceLine_vacio(self):
        invoice = build_gp_invoice(_doc(), [], "HQ01")
        self.assertEqual(invoice["vendorInvoiceLine"], [])

    def test_tipo_factura_doc_configurable(self):
        invoice = build_gp_invoice(_doc(), [_line()], "HQ01", tipo_factura_doc=3)
        self.assertEqual(invoice["tipoFacturaDoc"], 3)

    def test_fechas_oc_en_lineas(self):
        invoice = build_gp_invoice(
            _doc(), [_line()], "HQ01",
            tipo_factura_doc=2,
            fecha_requerida="2026-09-01T00:00:00",
            fecha_prometida="2026-10-15T00:00:00",
        )
        self.assertEqual(
            invoice["vendorInvoiceLine"][0]["fechaRequerida"],
            "2026-09-01T00:00:00",
        )
        self.assertEqual(
            invoice["vendorInvoiceLine"][0]["fechaPrometida"],
            "2026-10-15T00:00:00",
        )


class TestResolveGpTipo(unittest.TestCase):

    def test_servicio_prioridad_absoluta(self):
        self.assertEqual(resolve_gp_tipo(True, True), 3)
        self.assertEqual(resolve_gp_tipo(True, False), 3)

    def test_con_recepciones_tipo_envio(self):
        self.assertEqual(resolve_gp_tipo(False, True), 1)

    def test_sin_recepciones_tipo_envio_factura(self):
        self.assertEqual(resolve_gp_tipo(False, False), 2)


class TestConsolidateGpLines(unittest.TestCase):

    def _detail(self, codi, qty, valo):
        return {"nvpro_codi": codi, "nvdet_tcan": qty, "nvdet_valo": valo}

    def test_consolida_y_matchea_oc(self):
        oc = [
            {"item_code": "ITEM-GP-1", "idx": 1, "uom": "UN"},
            {"item_code": "ITEM-GP-2", "idx": 2, "uom": "UN"},
            {"item_code": "ITEM-GP-3", "idx": 3, "uom": "UN"},
        ]
        lines, missing = consolidate_gp_lines(
            [
                self._detail("SUP-1", 85, 31.58),
                self._detail("SUP-2", 40, 12.0),
            ],
            {"SUP-1": "ITEM-GP-1", "SUP-2": "ITEM-GP-2"},
            oc_items=oc,
            order_no="GP-PO-0001",
        )
        self.assertEqual(missing, [])
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["item_code"], "ITEM-GP-1")
        self.assertEqual(lines[0]["qty"], 85)
        self.assertAlmostEqual(lines[0]["rate"], 31.58)
        self.assertEqual(lines[0]["idx"], 1)
        self.assertEqual(lines[0]["uom"], "UN")
        self.assertEqual(lines[0]["order_no"], "GP-PO-0001")
        # mismo producto en dos lineas de factura -> una sola linea consolidada
        lines2, missing2 = consolidate_gp_lines(
            [
                self._detail("SUP-1", 50, 10.0),
                self._detail("SUP-1", 30, 10.0),
            ],
            {"SUP-1": "ITEM-GP-1"},
            oc_items=[{"item_code": "ITEM-GP-1", "idx": 1, "uom": "UN"}],
            order_no="GP-PO-0001",
        )
        self.assertEqual(len(lines2), 1)
        self.assertEqual(lines2[0]["qty"], 80)
        self.assertAlmostEqual(lines2[0]["rate"], 10.0)

    def test_producto_inexistente_en_oc_se_omite(self):
        oc = [{"item_code": "ITEM-GP-1", "idx": 1, "uom": "UN"}]
        lines, missing = consolidate_gp_lines(
            [
                self._detail("SUP-1", 10, 5.0),
                self._detail("SUP-X", 10, 5.0),
            ],
            {"SUP-1": "ITEM-GP-1", "SUP-X": "ITEM-NO-OC"},
            oc_items=oc,
        )
        # SUP-X homologa pero no esta en la OC -> se omite (no es missing)
        self.assertEqual(missing, [])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["item_code"], "ITEM-GP-1")

    def test_sin_oc_no_filtra_y_queda_idx_0(self):
        lines, missing = consolidate_gp_lines(
            [self._detail("SRV-1", 5, 100.0)],
            {"SRV-1": "ITEM-SRV-2"},
            oc_items=None,
            order_no="",
        )
        self.assertEqual(missing, [])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["item_code"], "ITEM-SRV-2")
        self.assertEqual(lines[0]["idx"], 0)
        self.assertEqual(lines[0]["order_no"], "")

    def test_codigos_sin_homologacion_son_missing(self):
        lines, missing = consolidate_gp_lines(
            [self._detail("SUP-9", 1, 1.0)],
            {},
            oc_items=None,
        )
        self.assertEqual(missing, ["SUP-9"])
        self.assertEqual(lines, [])


class TestMakeInvoiceBuilder(unittest.TestCase):

    def test_backend_gp_devuelve_builder_gp(self):
        builder = make_invoice_builder("documenteme", backend="GP")
        invoice = builder(_doc(), [_line()], "HQ01")
        self.assertIn("noFacturaProveedor", invoice)
        self.assertNotIn("NoFacturaProveedor", invoice)

    def test_default_bc_preserva_forma_original(self):
        builder = make_invoice_builder("documenteme")
        invoice = builder(_doc(), [_line()], "HQ01")
        self.assertEqual(invoice["NoFacturaProveedor"], "PRB002")
        self.assertIn("Almacen", invoice)
        self.assertEqual(invoice["Almacen"], "HQ01")
        self.assertEqual(invoice["puntofacturacion"], "estandar")

    def test_collection_mantiene_puntofacturacion_ds_soporte(self):
        builder = make_invoice_builder("collection")
        invoice = builder(_doc(), [_line()], "HQ01")
        self.assertEqual(invoice["puntofacturacion"], "DS SOPORTE")

    def test_build_payload_usa_builder_gp(self):
        payload = build_payload(
            [_doc()], lambda doc: ([_line()], ""),
            lambda po: "HQ01",
            build_invoice_fn=make_invoice_builder("documenteme", backend="GP"),
        )
        self.assertEqual(len(payload), 1)
        self.assertIn("noFacturaProveedor", payload[0])


class TestNormalizeGpResponse(unittest.TestCase):

    def test_status_fuera_de_rango_es_error_global(self):
        result = normalize_gp_response("server error", 500, num_invoices=1)
        self.assertEqual(result["Result"], 1)
        self.assertEqual(result["invoices"], [])

    def test_contrato_bc_se_reutiliza(self):
        response = {"Result": 0, "invoices": [{"doc_number": "0100", "error": ""}]}
        result = normalize_gp_response(response, 200, num_invoices=1)
        self.assertEqual(result, response)

    def test_respuesta_plana_extrae_doc_number(self):
        response = {"status": 200, "invoiceNumber": "0100"}
        result = normalize_gp_response(response, 200, num_invoices=2)
        self.assertEqual(result["Result"], 0)
        self.assertEqual([i["doc_number"] for i in result["invoices"]],
                         ["0100", "0100"])

    def test_sin_doc_number_es_error(self):
        result = normalize_gp_response({"status": 200}, 200, num_invoices=1)
        self.assertEqual(result["Result"], 1)
        self.assertIn("no devolvio documento", result["Description"])

    def test_extrae_error_descriptivo(self):
        response = {"status": 400, "Description": "Proveedor inexistente"}
        result = normalize_gp_response(response, 200, num_invoices=1)
        self.assertEqual(result["Result"], 1)
        self.assertEqual(result["Description"], "Proveedor inexistente")

    def test_exito_con_voucher_number(self):
        response = {
            "statusCode": "1",
            "description": "Invoice-Delivery number EA2026-003511 created successfully.",
            "voucherNumber": "EA2026-003511",
        }
        result = normalize_gp_response(response, 200, num_invoices=1)
        self.assertEqual(result["Result"], 0)
        self.assertEqual(result["invoices"][0]["doc_number"], "EA2026-003511")
        self.assertEqual(result["invoices"][0]["error"], "")

    def test_duplicado_status_996(self):
        response = {
            "statusCode": "996",
            "description": "Vendor Document numbers (VNDDOCNM) for "
                           "Shipment/Invoices (POPTYPE=3) must be unique",
            "voucherNumber": "",
        }
        result = normalize_gp_response(
            response, 400, num_invoices=1
        )
        self.assertEqual(result["Result"], 0)
        self.assertEqual(result["invoices"][0]["doc_number"], "")
        error = result["invoices"][0]["error"]
        self.assertIn("ya existe la factura", error.lower())
        self.assertIn("VNDDOCNM", error)

    def test_error_vendor_inexistente_status_2005(self):
        response = {
            "statusCode": "2005",
            "description": "Vendor Number (VENDORID) does not exist in the "
                           "Vendor Master Table - PM00200",
            "voucherNumber": "",
        }
        result = normalize_gp_response(
            response, 400, num_invoices=1
        )
        self.assertEqual(result["Result"], 1)
        self.assertEqual(result["invoices"], [])
        self.assertIn("Vendor Number (VENDORID)", result["Description"])

    def test_error_linea_recepcion_status_2061(self):
        response = {
            "statusCode": "2061",
            "description": "Receipt Line Number already exists",
            "voucherNumber": "",
        }
        result = normalize_gp_response(
            response, 400, num_invoices=1
        )
        self.assertEqual(result["Result"], 1)
        self.assertIn("Receipt Line Number", result["Description"])

    def test_exito_con_http_400_si_status_code_1(self):
        response = {
            "statusCode": "1",
            "description": "Invoice created",
            "voucherNumber": "EA2026-003512",
        }
        result = normalize_gp_response(response, 400, num_invoices=2)
        self.assertEqual(result["Result"], 0)
        self.assertEqual([i["doc_number"] for i in result["invoices"]],
                         ["EA2026-003512", "EA2026-003512"])

    def test_status_code_1_sin_voucher_es_error(self):
        response = {"statusCode": "1", "description": "ok", "voucherNumber": ""}
        result = normalize_gp_response(response, 200, num_invoices=1)
        self.assertEqual(result["Result"], 1)
        self.assertIn("no devolvio documento", result["Description"])

    def test_lista_de_resultados_se_mapea_por_indice(self):
        response = [
            {
                "statusCode": "1",
                "description": "created",
                "voucherNumber": "EA2026-003521",
            },
            {
                "statusCode": "2005",
                "description": "Vendor Number (VENDORID) does not exist",
                "voucherNumber": "",
            },
        ]
        result = normalize_gp_response(response, 200, num_invoices=2)
        self.assertEqual(result["Result"], 0)
        self.assertEqual(result["invoices"][0]["doc_number"], "EA2026-003521")
        self.assertEqual(result["invoices"][0]["error"], "")
        self.assertEqual(result["invoices"][1]["doc_number"], "")
        self.assertIn("Vendor Number (VENDORID)", result["invoices"][1]["error"])

    def test_sender_gp_retorna_200_cuando_result_0(self):
        from unittest.mock import patch

        response = {
            "statusCode": "996",
            "description": "Vendor Document numbers (VNDDOCNM) must be unique",
            "voucherNumber": "",
        }
        fake_authorize = MagicMock()
        fake_authorize.use_case.bearer.authorize.send_request_status \
            .return_value = (response, 400)
        with patch.dict(sys.modules, {
            "qp_authorization": fake_authorize,
            "qp_authorization.use_case": fake_authorize.use_case,
            "qp_authorization.use_case.bearer": fake_authorize.use_case.bearer,
            "qp_authorization.use_case.bearer.authorize":
                fake_authorize.use_case.bearer.authorize,
        }), patch("qp_supplier_front.services.utils.add_log"):
            normalized, status = send_purchase_invoice_request_gp(
                "create_purchase_order", [{"noFacturaProveedor": "FAC-1"}]
            )
        self.assertEqual(status, 200)
        self.assertEqual(normalized["Result"], 0)
        self.assertIn("ya existe la factura",
                      normalized["invoices"][0]["error"].lower())

    def test_sender_gp_envia_un_dict_por_factura(self):
        from unittest.mock import patch

        response = {
            "statusCode": "1",
            "description": "Invoice-Delivery number EA2026-003511 created "
                           "successfully.",
            "voucherNumber": "EA2026-003511",
        }
        fake_authorize = MagicMock()
        fake_authorize.use_case.bearer.authorize.send_request_status \
            .return_value = (response, 200)
        with patch.dict(sys.modules, {
            "qp_authorization": fake_authorize,
            "qp_authorization.use_case": fake_authorize.use_case,
            "qp_authorization.use_case.bearer": fake_authorize.use_case.bearer,
            "qp_authorization.use_case.bearer.authorize":
                fake_authorize.use_case.bearer.authorize,
        }), patch("qp_supplier_front.services.utils.add_log"):
            _, status = send_purchase_invoice_request_gp(
                "create_purchase_order",
                [
                    {"noFacturaProveedor": "FAC-1"},
                    {"noFacturaProveedor": "FAC-2"},
                ],
            )

        sender = fake_authorize.use_case.bearer.authorize.send_request_status
        self.assertEqual(sender.call_count, 2)
        first_payload = sender.call_args_list[0][1]["payload"]
        second_payload = sender.call_args_list[1][1]["payload"]
        self.assertNotIsInstance(first_payload, list)
        self.assertNotIsInstance(second_payload, list)
        self.assertEqual(first_payload, {"noFacturaProveedor": "FAC-1"})
        self.assertEqual(second_payload, {"noFacturaProveedor": "FAC-2"})
        self.assertEqual(status, 200)

    def test_sender_gp_vuelca_error_como_slot_individual(self):
        from unittest.mock import patch

        response = {
            "statusCode": "2005",
            "description": "Vendor Number (VENDORID) does not exist",
            "voucherNumber": "",
        }
        fake_authorize = MagicMock()
        fake_authorize.use_case.bearer.authorize.send_request_status \
            .return_value = (response, 400)
        with patch.dict(sys.modules, {
            "qp_authorization": fake_authorize,
            "qp_authorization.use_case": fake_authorize.use_case,
            "qp_authorization.use_case.bearer": fake_authorize.use_case.bearer,
            "qp_authorization.use_case.bearer.authorize":
                fake_authorize.use_case.bearer.authorize,
        }), patch("qp_supplier_front.services.utils.add_log"):
            normalized, status = send_purchase_invoice_request_gp(
                "create_purchase_order", [{"noFacturaProveedor": "FAC-1"}]
            )
        self.assertEqual(status, 200)
        self.assertEqual(normalized["Result"], 0)
        invoice = normalized["invoices"][0]
        self.assertEqual(invoice["doc_number"], "")
        self.assertIn("Vendor Number (VENDORID)", invoice["error"])


if __name__ == "__main__":
    unittest.main()