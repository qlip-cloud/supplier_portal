# -*- coding: utf-8 -*-
"""
test_collection_gp_approve.py
=============================
Pruebas de la creacion via GP de facturas de cuentas de cobro (collection):

- approve_collection_invoices con build_invoice_fn GP -> payload con la forma
  del endpoint alpla (noFacturaProveedor, fechas YYYY-MM-DDT00:00:00, linea
  unica con unidadMedida, puntofacturacion vacio, dimensionSetLines vacio).
- _persist_for_backend("GP") registra qp_creation_backend="GP".

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m unittest qp_supplier_front.tests.test_collection_gp_approve -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.uses_cases.collection_invoices import mapping  # noqa: E402
from qp_supplier_front.uses_cases.collection_invoices.approve import (  # noqa: E402
    approve_collection_invoices,
)
from qp_supplier_front.uses_cases.documenteme.approve import (  # noqa: E402
    make_invoice_builder,
)
from qp_supplier_front.resources.collection_accounts import (  # noqa: E402
    _collection_invoice_base as base,
)


def _doc(**overrides):
    data = {
        "name": "PI-1",
        "nvfac_nume": "N-1",
        "nvpro_ndoc": "999999999",
        "nvfac_fech": "2026-09-01",
        "nvfac_cufe": "",
        "nvfac_orde": "PO-1",
        "nvfac_stot": 600000,
        "nvfac_totp": 600000,
        "nvfac_conv": "2",
        "nvfac_esta": "V",
        "nvmon_codi": "COP",
        "collection_account": "CA-1",
    }
    data.update(overrides)
    return data


def _line():
    return mapping.build_single_line(
        {"item_code": "ITEM-1", "uom": "BOX", "idx": 5},
        600000,
        order_no="PO-1",
    )


class TestApproveCollectionGpPayload(unittest.TestCase):

    NOW = "2026-09-11 10:00:00"

    def _run(self):
        calls = {"sent": [], "persisted": [], "marked": []}
        docs = [_doc()]
        results = [{"doc_number": "GP1001", "error": ""}]

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
            return {"Result": 0, "invoices": results}, 200

        def persist_invoice_fn(doc, doc_number, now):
            calls["persisted"].append((doc.get("nvfac_nume"), doc_number))

        def mark_registered_fn(doc, doc_number):
            calls["marked"].append(doc.get("nvfac_nume"))

        result = approve_collection_invoices(
            ["PI-1"],
            get_docs_fn=lambda names: [d for d in docs if d.get("name") in names],
            get_lines_fn=lambda doc: ([_line()], ""),
            get_headquarter_fn=lambda po: "HQ01",
            po_exists_fn=lambda po: True,
            receipt_bank_fn=lambda po: [{
                "name": "R1", "amount": 600000, "date": "", "qp_invoice": None,
            }],
            send_request_fn=send_request_fn,
            parse_doc_numbers_fn=lambda resp: resp.get("invoices") or [],
            persist_invoice_fn=persist_invoice_fn,
            mark_registered_fn=mark_registered_fn,
            mark_error_fn=lambda doc, error: None,
            commit_fn=lambda: None,
            now=self.NOW,
            build_invoice_fn=make_invoice_builder("collection", backend="GP"),
        )
        return calls, result

    def test_envia_payload_gp(self):
        calls, result = self._run()

        self.assertEqual(len(result["approved"]), 1)
        endpoint_code, payload = calls["sent"][0]
        self.assertEqual(endpoint_code, "create_purchase_order")

        invoice = payload[0]
        self.assertEqual(invoice["noFacturaProveedor"], "N-1")
        self.assertEqual(invoice["invoiceDate"], "2026-09-01T00:00:00")
        self.assertEqual(invoice["postingDate"], "2026-09-01T00:00:00")
        self.assertEqual(invoice["puntofacturacion"], "")
        self.assertEqual(invoice["numeroPord"], "PO-1")
        self.assertEqual(invoice["dimensionSetLines"], [])
        self.assertEqual(invoice["cufe"], "")
        self.assertEqual(invoice["descripcion"], "N-1")

        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["noProducto"], "ITEM-1")
        self.assertEqual(line["unidadMedida"], "BOX")
        self.assertEqual(line["noLineaRecepcion"], 5)
        self.assertEqual(line["noRecepcion"], "PO-1")
        self.assertEqual(line["noPedido"], "")

    def test_persiste_y_marca(self):
        calls, _result = self._run()
        self.assertEqual(calls["persisted"], [("N-1", "GP1001")])
        self.assertEqual(calls["marked"], ["N-1"])


class TestPersistForBackend(unittest.TestCase):

    def test_persist_gp_registra_backend(self):
        doc = _doc()
        frappe_mock = MagicMock()
        with patch.object(base, "frappe", frappe_mock):
            with patch.object(base, "resolve_open_notifications"):
                with patch.object(base, "mark_collection_account_invoiced"):
                    persist = base._persist_for_backend("GP")
                    persist(doc, "GP1001", "2026-09-11 10:00:00")

        args = frappe_mock.db.set_value.call_args[0]
        self.assertEqual(args[0], "qp_SP_PurchaseInvoice")
        self.assertEqual(args[1], "PI-1")
        self.assertEqual(args[2]["qp_creation_backend"], "GP")
        self.assertEqual(args[2]["invoice_id"], "GP1001")
        self.assertEqual(args[2]["qp_status"], "BCC")

    def test_persist_gp_crea_referencia_purchase_invoice_bc(self):
        doc = _doc()
        frappe_mock = MagicMock()
        frappe_mock.db.exists = MagicMock(return_value=False)
        with patch.object(base, "frappe", frappe_mock):
            with patch.object(base, "resolve_open_notifications"):
                with patch.object(base, "mark_collection_account_invoiced"):
                    persist = base._persist_for_backend("GP")
                    persist(doc, "GP1001", "2026-09-11 10:00:00")

        inserted = frappe_mock.get_doc.call_args[0][0]
        self.assertEqual(inserted["doctype"], "qp_SP_PurchaseInvoiceBC")
        self.assertEqual(inserted["invoice_id"], "GP1001")
        self.assertEqual(inserted["purchase_invoice"], "PI-1")

    def test_persist_bc_no_crea_referencia(self):
        doc = _doc()
        frappe_mock = MagicMock()
        with patch.object(base, "frappe", frappe_mock):
            with patch.object(base, "resolve_open_notifications"):
                with patch.object(base, "mark_collection_account_invoiced"):
                    persist = base._persist_for_backend("BC")
                    persist(doc, "BC1001", "2026-09-11 10:00:00")

        frappe_mock.get_doc.assert_not_called()


class TestMarkDuplicateBackend(unittest.TestCase):

    def test_mark_duplicate_gp_nombra_gp(self):
        doc = _doc()
        frappe_mock = MagicMock()
        with patch.object(base, "frappe", frappe_mock):
            with patch.object(base, "insert_notification") as insert_notification:
                with patch.object(base, "mark_collection_account_invoiced"):
                    base.mark_duplicate_registered(
                        doc, "VNDDOCNM duplicado", "2026-09-11 10:00:00",
                        backend="GP",
                    )

        args = frappe_mock.db.set_value.call_args[0]
        message = args[2]["qp_error_message"]
        self.assertEqual(args[2]["qp_status"], "BCC")
        self.assertEqual(args[2]["qp_creation_backend"], "GP")
        self.assertIn("en GP", message)
        self.assertIn("VNDDOCNM duplicado", message)

        notification = insert_notification.call_args[0]
        self.assertEqual(notification[1], message)

    def test_mark_duplicate_bc_nombra_bc(self):
        doc = _doc()
        frappe_mock = MagicMock()
        with patch.object(base, "frappe", frappe_mock):
            with patch.object(base, "insert_notification"):
                with patch.object(base, "mark_collection_account_invoiced"):
                    base.mark_duplicate_registered(
                        doc, "ya existe la factura", "2026-09-11 10:00:00",
                        backend="BC",
                    )

        args = frappe_mock.db.set_value.call_args[0]
        self.assertEqual(args[2]["qp_creation_backend"], "BC")
        self.assertIn("en BC", args[2]["qp_error_message"])

    def test_mark_duplicate_for_backend_envuelve(self):
        doc = _doc()
        frappe_mock = MagicMock()
        with patch.object(base, "frappe", frappe_mock):
            with patch.object(base, "insert_notification"):
                with patch.object(base, "mark_collection_account_invoiced"):
                    mark = base._mark_duplicate_for_backend("GP")
                    mark(doc, "error x", "2026-09-11 10:00:00")

        args = frappe_mock.db.set_value.call_args[0]
        self.assertEqual(args[2]["qp_creation_backend"], "GP")


if __name__ == "__main__":
    unittest.main()