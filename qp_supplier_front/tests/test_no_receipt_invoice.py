# -*- coding: utf-8 -*-
"""
test_no_receipt_invoice.py
==========================
Facturas BC sin orden de compra ni recepcion (home delivery y facturas sin
OC) que se crean con el endpoint `create_purchase_noreceipt`.

Cubre:
- Payload estricto del endpoint nuevo (Invoice / Credit Memo).
- Resolucion del endpoint por documento (noreceipt / order / nc).
- Que las facturas con OC conserven el payload y el endpoint historicos.

Ejecutar con:
  python -m unittest qp_supplier_front.tests.test_no_receipt_invoice -v
"""
import unittest

from qp_supplier_front.constant.endpoint import (
    CREATE_PURCHASE_NC,
    CREATE_PURCHASE_NORECEIPT,
    CREATE_PURCHASE_ORDER,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    _build_invoice,
    _build_no_receipt_invoice,
    approve_documents,
    make_invoice_builder,
    resolve_endpoint_code,
)

DELIVERY_DOC = {
    "name": "D1",
    "nvfac_fech": "2026-11-03 00:00:00",
    "nvpro_ndoc": "900162414",
    "nvfac_nume": "FV-001",
    "nvfac_cufe": "cufe-1",
    "nvfac_orde": "",
}
DELIVERY_LINES = [{"item_code": "DEL-01", "qty": 1, "rate": 250000.0}]

INVOICE_KEYS = {
    "DocumentType",
    "invoiceDate",
    "postingDate",
    "vendorNumber",
    "puntofacturacion",
    "NoFacturaProveedor",
    "Categoria",
    "SubCategoria",
    "Cufe",
    "Almacen",
    "tipoFacturaDoc",
    "formaPago",
    "NoFacturaAfectada",
    "dimensionSetLines",
    "vendorInvoiceLine",
}

LINE_KEYS = {"NoProducto", "cantidad", "Precio", "Type", "Comentarios"}


class TestNoReceiptPayload(unittest.TestCase):

    def test_invoice_tiene_solo_los_campos_del_endpoint(self):
        invoice = _build_invoice(
            DELIVERY_DOC, DELIVERY_LINES, "", no_receipt=True
        )
        self.assertEqual(set(invoice.keys()), INVOICE_KEYS)

    def test_invoice_cabecera(self):
        invoice = _build_invoice(
            DELIVERY_DOC, DELIVERY_LINES, "", no_receipt=True
        )
        self.assertEqual(invoice["DocumentType"], "Invoice")
        self.assertEqual(invoice["invoiceDate"], "2026-11-03")
        self.assertEqual(invoice["postingDate"], "2026-11-03")
        self.assertEqual(invoice["vendorNumber"], "900162414")
        self.assertEqual(invoice["puntofacturacion"], "estandar")
        self.assertEqual(invoice["NoFacturaProveedor"], "FV-001")
        self.assertEqual(invoice["tipoFacturaDoc"], "Estándar")
        self.assertEqual(invoice["Categoria"], "")
        self.assertEqual(invoice["SubCategoria"], "")
        self.assertEqual(invoice["Cufe"], "cufe-1")
        self.assertEqual(invoice["Almacen"], "")
        self.assertEqual(invoice["formaPago"], "")
        self.assertEqual(invoice["NoFacturaAfectada"], "")
        self.assertEqual(
            invoice["dimensionSetLines"],
            [{"code": "TERCERO", "valueCode": "900162414"}],
        )

    def test_invoice_linea_sin_recepcion_ni_pedido(self):
        invoice = _build_invoice(
            DELIVERY_DOC, DELIVERY_LINES, "", no_receipt=True
        )
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(set(line.keys()), LINE_KEYS)
        self.assertEqual(line["NoProducto"], "DEL-01")
        self.assertEqual(line["cantidad"], 1)
        self.assertEqual(line["Precio"], 250000.0)
        self.assertEqual(line["Type"], "Item")
        self.assertEqual(line["Comentarios"], "")

    def test_invoice_comentario_marcado_para_bc(self):
        doc = dict(DELIVERY_DOC)
        doc["qp_bc_comment"] = "Factura de home delivery"
        doc["qp_bc_comment_url"] = "https://x/files/a.pdf"
        invoice = _build_invoice(doc, DELIVERY_LINES, "", no_receipt=True)
        self.assertEqual(
            invoice["vendorInvoiceLine"][0]["Comentarios"],
            "ALERTA::https://x/files/a.pdf:Factura de home delivery",
        )

    def test_credit_memo(self):
        doc = {
            "nvfac_fech": "2026-11-03 00:00:00",
            "nvpro_ndoc": "900162414",
            "nvfac_nume": "NC-001",
            "nvfac_cufe": "",
            "nvtip_docu": "C",
            "qp_ref_invoice": "FC70071",
        }
        invoice = _build_no_receipt_invoice(doc, DELIVERY_LINES, "")
        self.assertEqual(set(invoice.keys()), INVOICE_KEYS)
        self.assertEqual(invoice["DocumentType"], "Credit Memo")
        self.assertEqual(invoice["puntofacturacion"], "")
        self.assertEqual(invoice["tipoFacturaDoc"], "")
        self.assertEqual(invoice["NoFacturaAfectada"], "FC70071")
        self.assertEqual(invoice["NoFacturaProveedor"], "NC-001")
        self.assertEqual(invoice["vendorInvoiceLine"][0]["Type"], "Item")

    def test_sin_no_receipt_conserva_payload_actual(self):
        doc = dict(DELIVERY_DOC)
        doc["nvfac_orde"] = ""
        invoice = _build_invoice(doc, DELIVERY_LINES, "", no_receipt=False)
        self.assertNotIn("DocumentType", invoice)
        self.assertIn("NoPedidoProveedor", invoice)
        line = invoice["vendorInvoiceLine"][0]
        self.assertIn("NoRecepcion", line)
        self.assertIn("NoLineaRecepcion", line)
        self.assertIn("NoPedido", line)

    def test_con_oc_conserva_payload_actual(self):
        doc = dict(DELIVERY_DOC)
        doc["nvfac_orde"] = "OC-123"
        lines = [
            {"item_code": "ITEM-1", "qty": 2, "rate": 10,
             "receiving_no": "", "order_no": "OC-123"},
        ]
        invoice = _build_invoice(doc, lines, "", no_receipt=True)
        self.assertNotIn("DocumentType", invoice)
        self.assertEqual(invoice["NoPedidoProveedor"], "OC-123")
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["NoPedido"], "OC-123")
        self.assertEqual(line["NoRecepcion"], "")


class TestMakeInvoiceBuilder(unittest.TestCase):

    def test_documenteme_activa_el_payload_nuevo(self):
        builder = make_invoice_builder("documenteme", no_receipt=True)
        invoice = builder(dict(DELIVERY_DOC), DELIVERY_LINES, "")
        self.assertEqual(invoice["DocumentType"], "Invoice")

    def test_collection_mantiene_el_payload_actual(self):
        builder = make_invoice_builder("collection")
        invoice = builder(dict(DELIVERY_DOC), DELIVERY_LINES, "")
        self.assertNotIn("DocumentType", invoice)
        self.assertEqual(invoice["puntofacturacion"], "DS SOPORTE")


class TestResolveEndpointCode(unittest.TestCase):

    def test_delivery_usa_noreceipt(self):
        doc = {"nvfac_orde": "entregapaciente009"}
        self.assertEqual(
            resolve_endpoint_code(doc, lambda d: True),
            CREATE_PURCHASE_NORECEIPT,
        )

    def test_sin_oc_usa_noreceipt(self):
        self.assertEqual(
            resolve_endpoint_code({"nvfac_orde": ""}, None),
            CREATE_PURCHASE_NORECEIPT,
        )
        self.assertEqual(
            resolve_endpoint_code({}, None), CREATE_PURCHASE_NORECEIPT
        )
        self.assertEqual(
            resolve_endpoint_code({"nvfac_orde": " , "}, None),
            CREATE_PURCHASE_NORECEIPT,
        )

    def test_con_oc_usa_el_endpoint_historico(self):
        self.assertEqual(
            resolve_endpoint_code({"nvfac_orde": "OC-123"}, None),
            CREATE_PURCHASE_ORDER,
        )
        self.assertEqual(
            resolve_endpoint_code(
                {"nvfac_orde": "OC-1, OC-2"}, lambda d: False
            ),
            CREATE_PURCHASE_ORDER,
        )

    def test_nota_credito_usa_su_endpoint(self):
        doc = {"nvfac_orde": "", "nvtip_docu": "C"}
        self.assertEqual(
            resolve_endpoint_code(doc, None), CREATE_PURCHASE_NC
        )
        self.assertEqual(
            resolve_endpoint_code(doc, lambda d: True), CREATE_PURCHASE_NC
        )


class TestApproveRouting(unittest.TestCase):

    def _run(self, docs):
        calls = []

        def send_request_fn(endpoint_code, payload):
            calls.append((endpoint_code, [item["doc"] for item in payload]))
            return {
                "Result": 0,
                "invoices": [
                    {"doc_number": "D-{}".format(item["doc"]), "error": ""}
                    for item in payload
                ],
            }, 200

        result = approve_documents(
            list(docs.keys()),
            get_docs_fn=lambda names: [docs[name] for name in names],
            get_lines_fn=lambda doc: ([], ""),
            get_headquarter_fn=lambda po: "",
            po_exists_fn=lambda po: True,
            send_request_fn=send_request_fn,
            parse_doc_numbers_fn=lambda response: response["invoices"],
            persist_invoice_fn=lambda doc, number, now: None,
            mark_registered_fn=lambda doc, number: None,
            mark_error_fn=lambda doc, error: None,
            commit_fn=lambda: None,
            now="2026-11-03 00:00:00",
            force=True,
            build_invoice_fn=lambda doc, lines, hq: {"doc": doc["name"]},
            endpoint_for_doc_fn=lambda doc: resolve_endpoint_code(
                doc, lambda d: bool(d.get("is_delivery"))
            ),
        )
        return calls, result

    def test_lote_mixto_separa_delivery_y_orden(self):
        docs = {
            "d1": {"name": "d1", "nvfac_esta": "V", "is_delivery": True},
            "f1": {"name": "f1", "nvfac_esta": "V", "nvfac_orde": "OC-1"},
        }
        calls, result = self._run(docs)
        self.assertEqual(
            calls,
            [
                (CREATE_PURCHASE_NORECEIPT, ["d1"]),
                (CREATE_PURCHASE_ORDER, ["f1"]),
            ],
        )
        self.assertEqual(
            sorted(item["name"] for item in result["approved"]),
            ["d1", "f1"],
        )


if __name__ == "__main__":
    unittest.main()
