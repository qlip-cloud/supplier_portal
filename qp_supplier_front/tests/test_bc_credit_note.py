# -*- coding: utf-8 -*-
"""
test_bc_credit_note.py
======================
Pruebas del flujo BC de notas credito (nucleo puro):

- credit_note_bc.resolve_credit_note_lines (emparejamiento NC vs recepcion/OC).
- _build_credit_note (payload del endpoint create_purchase_nc).
- Agrupacion por endpoint del lote mixto (facturas + NC).

Ejecutar con:
  python -m unittest qp_supplier_front.tests.test_bc_credit_note -v
"""
import unittest

from qp_supplier_front.constant.endpoint import (
    CREATE_PURCHASE_NC,
    CREATE_PURCHASE_ORDER,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    _build_invoice,
    _group_payload,
    _send_grouped_payloads,
    approve_documents,
)
from qp_supplier_front.uses_cases.documenteme.credit_note_bc import (
    resolve_credit_note_lines,
)


class TestResolveCreditNoteLines(unittest.TestCase):

    def test_empareja_por_codigo(self):
        lines, error = resolve_credit_note_lines(
            [{"item_code": "OP0080", "qty": 2, "rate": 100}],
            [{"item_code": "OP0080", "item_name": "Producto 80"}],
        )
        self.assertEqual(error, "")
        self.assertEqual(lines[0]["item_code"], "OP0080")
        self.assertEqual(lines[0]["qty"], 2)
        self.assertEqual(lines[0]["rate"], 100)
        self.assertEqual(lines[0]["type"], "Item")

    def test_empareja_por_descripcion(self):
        lines, error = resolve_credit_note_lines(
            [{"item_code": "SUP-1", "description": "Producto 80",
              "qty": 1, "rate": 50}],
            [{"item_code": "OP0080", "item_name": "Producto 80"}],
        )
        self.assertEqual(error, "")
        self.assertEqual(lines[0]["item_code"], "OP0080")

    def test_empareja_unica_candidata(self):
        lines, error = resolve_credit_note_lines(
            [{"item_code": "X", "qty": 1, "rate": 10}],
            [{"item_code": "OP0080"}],
        )
        self.assertEqual(error, "")
        self.assertEqual(lines[0]["item_code"], "OP0080")

    def test_asignacion_posicional_con_varias_lineas(self):
        lines, error = resolve_credit_note_lines(
            [
                {"item_code": "A", "qty": 1, "rate": 10},
                {"item_code": "B", "qty": 2, "rate": 20},
            ],
            [
                {"item_code": "OP-A"},
                {"item_code": "OP-B"},
            ],
        )
        self.assertEqual(error, "")
        self.assertEqual([line["item_code"] for line in lines], ["OP-A", "OP-B"])

    def test_error_si_es_ambiguo(self):
        lines, error = resolve_credit_note_lines(
            [{"item_code": "Z", "qty": 1, "rate": 10}],
            [{"item_code": "OP-A"}, {"item_code": "OP-B"}],
        )
        self.assertEqual(lines, [])
        self.assertIn("No se pudo resolver", error)

    def test_error_sin_banco(self):
        lines, error = resolve_credit_note_lines(
            [{"item_code": "A", "qty": 1, "rate": 10}], []
        )
        self.assertEqual(lines, [])
        self.assertIn("no tiene recepciones", error)


class TestBuildCreditNote(unittest.TestCase):

    def test_payload_nc(self):
        doc = {
            "nvfac_fech": "2026-10-28 00:00:00",
            "nvpro_ndoc": "900162414",
            "nvfac_nume": "EjemploYD",
            "qp_ref_invoice": "FC70065",
            "nvtip_docu": "C",
        }
        lines = [{"item_code": "OP0080", "qty": 1, "rate": 200000.0,
                  "type": "Item"}]
        invoice = _build_invoice(doc, lines, "")
        self.assertEqual(invoice["invoiceDate"], "2026-10-28")
        self.assertEqual(invoice["vendorNumber"], "900162414")
        self.assertEqual(invoice["NoNotaCreditoProveedor"], "EjemploYD")
        self.assertEqual(invoice["NoFacturaAfectada"], "FC70065")
        self.assertNotIn("NoFacturaProveedor", invoice)
        self.assertNotIn("NoPedidoProveedor", invoice)
        self.assertEqual(invoice["dimensionSetLines"][0]["code"], "TERCERO")
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["NoProducto"], "OP0080")
        self.assertEqual(line["Type"], "Item")
        self.assertEqual(line["Precio"], 200000.0)


class TestEndpointGrouping(unittest.TestCase):

    def _endpoint(self, doc):
        return (
            CREATE_PURCHASE_NC if doc.get("nvtip_docu") == "C"
            else CREATE_PURCHASE_ORDER
        )

    def test_agrupa_por_endpoint_conservando_orden(self):
        docs = [
            {"name": "f1"},
            {"name": "nc1", "nvtip_docu": "C"},
            {"name": "f2"},
        ]
        payload = ["p-f1", "p-nc1", "p-f2"]
        groups = _group_payload(docs, payload, self._endpoint)
        by_endpoint = {group["endpoint"]: group for group in groups}
        self.assertEqual(
            by_endpoint[CREATE_PURCHASE_ORDER]["indexes"], [0, 2]
        )
        self.assertEqual(
            by_endpoint[CREATE_PURCHASE_ORDER]["payload"], ["p-f1", "p-f2"]
        )
        self.assertEqual(by_endpoint[CREATE_PURCHASE_NC]["indexes"], [1])

    def test_sin_mapeador_es_un_solo_grupo(self):
        groups = _group_payload([{"name": "f1"}], ["p"], None)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["endpoint"], CREATE_PURCHASE_ORDER)

    def test_resultados_alineados_por_grupo(self):
        groups = [
            {"endpoint": CREATE_PURCHASE_ORDER, "indexes": [0, 2],
             "payload": ["p0", "p2"]},
            {"endpoint": CREATE_PURCHASE_NC, "indexes": [1],
             "payload": ["p1"]},
        ]
        calls = []

        def send_request_fn(endpoint_code, payload):
            calls.append((endpoint_code, payload))
            return {
                "Result": 0,
                "invoices": [
                    {"doc_number": "D{}".format(i), "error": ""}
                    for i in range(len(payload))
                ],
            }, 200

        results = _send_grouped_payloads(
            groups, send_request_fn, lambda response: response["invoices"]
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual([r["doc_number"] for r in results],
                         ["D0", "D0", "D1"])

    def test_lote_mixto_envia_cada_endpoint(self):
        docs = {
            "f1": {"name": "f1", "nvfac_nume": "F1", "nvfac_esta": "V"},
            "nc1": {"name": "nc1", "nvfac_nume": "NC1", "nvfac_esta": "V",
                    "nvtip_docu": "C"},
        }
        calls = []
        persisted = []

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
            ["f1", "nc1"],
            get_docs_fn=lambda names: [docs[name] for name in names],
            get_lines_fn=lambda doc: ([], ""),
            get_headquarter_fn=lambda po: "",
            po_exists_fn=lambda po: True,
            send_request_fn=send_request_fn,
            parse_doc_numbers_fn=lambda response: response["invoices"],
            persist_invoice_fn=lambda doc, number, now: persisted.append(
                (doc["name"], number)
            ),
            mark_registered_fn=lambda doc, number: None,
            mark_error_fn=lambda doc, error: None,
            commit_fn=lambda: None,
            now="2026-10-28 00:00:00",
            force=True,
            build_invoice_fn=lambda doc, lines, hq: {"doc": doc["name"]},
            endpoint_for_doc_fn=self._endpoint,
        )

        self.assertEqual(
            calls,
            [
                (CREATE_PURCHASE_ORDER, ["f1"]),
                (CREATE_PURCHASE_NC, ["nc1"]),
            ],
        )
        self.assertEqual(
            sorted(item["name"] for item in result["approved"]),
            ["f1", "nc1"],
        )
        self.assertEqual(
            sorted(persisted), [("f1", "D-f1"), ("nc1", "D-nc1")]
        )


if __name__ == "__main__":
    unittest.main()
