# -*- coding: utf-8 -*-
"""
test_enrich_document_detail.py
===============================
Pruebas unitarias para services/enrich_document_detail.py.

Aisladas de la base de datos: frappe se inyecta en sys.modules como mock.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_enrich_document_detail.py -v
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

from qp_supplier_front.services.enrich_document_detail import (
    build_po_products,
    sum_amounts_by_parent,
    build_receipt_products,
    enrich_document_detail,
)


class TestPureHelpers(unittest.TestCase):

    def test_build_po_products_mapea_campos(self):
        items = [
            {"item_code": "SH00086", "uom": "UN", "qty": 1, "rate": 1000, "amount": 1000},
            {"item_code": "SH00087", "uom": "CAJA", "qty": 2, "rate": 500, "amount": 1000},
        ]
        products = build_po_products(items)
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0], {
            "codigo": "SH00086",
            "udm": "UN",
            "cantidad": 1,
            "valor_unitario": 1000,
            "valor_total": 1000,
        })
        self.assertEqual(products[1]["codigo"], "SH00087")

    def test_build_po_products_sin_items(self):
        self.assertEqual(build_po_products([]), [])

    def test_sum_amounts_by_parent_agrupa_y_suma(self):
        child_items = [
            {"parent": "REC1:9001", "qp_amount": 1000},
            {"parent": "REC2:9001", "qp_amount": 500},
            {"parent": "REC1:9001", "qp_amount": 250},
            {"parent": "REC3:9001", "qp_amount": None},
        ]
        result = sum_amounts_by_parent(child_items)
        self.assertEqual(result, {
            "REC1:9001": 1250,
            "REC2:9001": 500,
            "REC3:9001": 0,
        })

    def test_build_receipt_products_usa_monto_por_factura(self):
        receipts = [
            {"name": "REC1:9001", "qp_receipt_id": "REC1"},
            {"name": "REC2:9001", "qp_receipt_id": "REC2"},
        ]
        applied_by_parent = {"REC1:9001": 1250, "REC2:9001": 500}
        products = build_receipt_products(receipts, applied_by_parent)
        self.assertEqual(products, [
            {"codigo": "REC1", "udm": "", "cantidad": 1,
             "valor_unitario": 1250, "valor_total": 1250},
            {"codigo": "REC2", "udm": "", "cantidad": 1,
             "valor_unitario": 500, "valor_total": 500},
        ])

    def test_build_receipt_products_recibo_sin_monto(self):
        receipts = [{"name": "REC1:9001", "qp_receipt_id": "REC1"}]
        products = build_receipt_products(receipts, {})
        self.assertEqual(products[0]["valor_total"], 0)


class TestEnrichDocumentDetail(unittest.TestCase):

    def _make_document(self, nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E", name="DOC1"):
        return {
            "name": name,
            "nvfac_nume": name,
            "nvfac_orde": nvfac_orde,
            "nvfac_rece": "REC222",
            "nvfac_totp": nvfac_totp,
            "nvfac_esta": nvfac_esta,
        }

    def _mock_frappe(self, po_exists=True, po_items=None, child_items=None, receipts=None):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = po_exists
        po_items = po_items if po_items is not None else [
            {"item_code": "SH00086", "uom": "UN", "qty": 1, "rate": 1000, "amount": 1000}
        ]
        child_items = child_items if child_items is not None else [
            {"parent": "REC1:9001", "qp_amount": 1000}
        ]
        receipts = receipts if receipts is not None else [
            {"name": "REC1:9001", "qp_receipt_id": "REC1",
             "qp_posting_date": "2026-07-16", "qp_description": "pago"}
        ]

        def _get_all(doctype, filters=None, fields=None):
            if doctype == "Purchase Order Item":
                return po_items
            if doctype == "qp_SP_PaymentReceiptItem":
                return child_items
            if doctype == "qp_SP_PaymentReceipt":
                return receipts
            return []

        frappe_mock.get_all.side_effect = _get_all
        return frappe_mock

    def _run(self, document, frappe_mock):
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            enrich_document_detail(document)
        return document

    def test_con_oc_y_recibos_poblados(self):
        frappe_mock = self._mock_frappe()
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["ordenes_compra"], ["OC111"])
        self.assertEqual(len(document["productos_orden_compra"]), 1)
        self.assertEqual(document["productos_orden_compra"][0]["codigo"], "SH00086")
        self.assertEqual(document["recepciones"], ["REC1"])
        self.assertEqual(document["productos_recepcion"][0]["valor_total"], 1000)

    def test_sin_oc_registrada_no_se_muestra_oc(self):
        frappe_mock = self._mock_frappe(po_exists=False)
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["ordenes_compra"], [])
        self.assertEqual(document["productos_orden_compra"], [])
        frappe_mock.db.exists.assert_called_once_with("Purchase Order", "OC111")

    def test_sin_recibos_asociados(self):
        frappe_mock = self._mock_frappe(child_items=[])
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["recepciones"], [])
        self.assertEqual(document["productos_recepcion"], [])
        self.assertEqual(document["nvfac_esta"], "E")

    def test_sin_nvfac_orde_las_listas_quedan_vacias(self):
        frappe_mock = self._mock_frappe()
        document = self._make_document(nvfac_orde=None, nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        frappe_mock.db.exists.assert_not_called()
        self.assertEqual(document["ordenes_compra"], [])
        self.assertEqual(document["recepciones"], [])
        self.assertEqual(document["productos_orden_compra"], [])
        self.assertEqual(document["productos_recepcion"], [])

    def test_se_pasa_a_registrado_cuando_sumatoria_cubre_total(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            child_items=[
                {"parent": "REC1:9001", "qp_amount": 600},
                {"parent": "REC2:9001", "qp_amount": 400},
            ],
            receipts=[
                {"name": "REC1:9001", "qp_receipt_id": "REC1",
                 "qp_posting_date": "2026-07-16", "qp_description": "pago"},
                {"name": "REC2:9001", "qp_receipt_id": "REC2",
                 "qp_posting_date": "2026-07-17", "qp_description": "pago"},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "A")
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "DOC1", "nvfac_esta", "A"
        )

    def test_no_cambia_estado_cuando_sumatoria_no_cubre_total(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            child_items=[
                {"parent": "REC1:9001", "qp_amount": 400},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "E")
        frappe_mock.db.set_value.assert_not_called()

    def test_no_reescribe_estado_registrado(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            child_items=[
                {"parent": "REC1:9001", "qp_amount": 1000},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="A")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "A")
        frappe_mock.db.set_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
