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
from datetime import datetime
from unittest.mock import patch, MagicMock

from qp_supplier_front.services.enrich_document_detail import (
    build_alert_tooltip,
    build_po_products,
    build_receipt_products,
    enrich_document_detail,
)


class TestPureHelpers(unittest.TestCase):

    def test_build_po_products_mapea_campos(self):
        items = [
            {"item_code": "SH00086", "uom": "UN", "qty": 1, "qp_unit_cost": 1000, "qp_extd_cost": 1000},
            {"item_code": "SH00087", "uom": "CAJA", "qty": 2, "qp_unit_cost": 500, "qp_extd_cost": 1000},
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

    def test_build_receipt_products_usa_rate_y_amount_por_item(self):
        items = [
            {"item_code": "SH00086", "uom": "UN", "qty": 1, "rate": 1000, "amount": 1000},
            {"item_code": "SH00087", "uom": "CAJA", "qty": 2, "rate": 500, "amount": 1000},
        ]
        products = build_receipt_products(items)
        self.assertEqual(products, [
            {"codigo": "SH00086", "udm": "UN", "cantidad": 1,
             "valor_unitario": 1000, "valor_total": 1000},
            {"codigo": "SH00087", "udm": "CAJA", "cantidad": 2,
             "valor_unitario": 500, "valor_total": 1000},
        ])

    def test_build_receipt_products_sin_amount_retorna_none(self):
        items = [{"item_code": "SH00086", "uom": "UN", "qty": 1, "rate": 1000}]
        products = build_receipt_products(items)
        self.assertIsNone(products[0]["valor_total"])


class TestBuildAlertTooltip(unittest.TestCase):

    def test_sin_alertas_retorna_none(self):
        self.assertIsNone(build_alert_tooltip([]))

    def test_arma_tooltip_multilinea(self):
        alerts = [
            {"alert_date": "2026-08-13 10:00:00", "alert_message": "Error en BC"},
            {"alert_date": "2026-08-13 11:00:00", "alert_message": "Ya existe"},
        ]
        tooltip = build_alert_tooltip(alerts)
        self.assertIn("Alertas:", tooltip)
        self.assertIn("2026-08-13 10:00", tooltip)
        self.assertIn("Error en BC", tooltip)
        self.assertIn("Ya existe", tooltip)

    def test_arma_tooltip_con_alert_date_datetime(self):
        alerts = [
            {"alert_date": datetime(2026, 8, 13, 10, 0, 0), "alert_message": "Error en BC"},
        ]
        tooltip = build_alert_tooltip(alerts)
        self.assertIn("2026-08-13 10:00", tooltip)
        self.assertIn("Error en BC", tooltip)


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

    def _mock_frappe(self, po_exists=True, po_items=None, receipts=None, alerts=None, receipt_items=None):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = po_exists
        po_items = po_items if po_items is not None else [
            {"item_code": "SH00086", "uom": "UN", "qty": 1, "qp_unit_cost": 1000, "qp_extd_cost": 1000}
        ]
        receipts = receipts if receipts is not None else [
            {"name": "REC1:9001", "supplier_delivery_note": "REC1",
             "posting_date": "2026-07-16", "total": 1000}
        ]
        if receipt_items is None:
            receipt_items = [
                {"item_code": "SH00086", "uom": "UN", "qty": 1,
                 "rate": receipt.get("total") or 0,
                 "amount": receipt.get("total") or 0}
                for receipt in receipts
            ]
        alerts = alerts if alerts is not None else []

        def _get_all(doctype, filters=None, fields=None, order_by=None):
            if doctype == "Purchase Order Item":
                return po_items
            if doctype == "Purchase Receipt":
                return receipts
            if doctype == "Purchase Receipt Item":
                return receipt_items
            if doctype == "qp_SP_Alert":
                return alerts
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

    def test_con_alertas_abiertas_muestra_tooltip(self):
        frappe_mock = self._mock_frappe(alerts=[
            {"alert_date": "2026-08-13 10:00:00", "alert_message": "Error en BC"},
        ])
        document = self._make_document()
        self._run(document, frappe_mock)

        self.assertTrue(document["has_alert"])
        self.assertIn("Error en BC", document["alert_tooltip"])

    def test_sin_alertas_no_muestra_tooltip(self):
        frappe_mock = self._mock_frappe(alerts=[])
        document = self._make_document()
        self._run(document, frappe_mock)

        self.assertFalse(document["has_alert"])
        self.assertIsNone(document["alert_tooltip"])

    def test_sin_oc_registrada_no_se_muestra_oc(self):
        frappe_mock = self._mock_frappe(po_exists=False)
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["ordenes_compra"], [])
        self.assertEqual(document["productos_orden_compra"], [])
        frappe_mock.db.exists.assert_called_once_with("Purchase Order", "OC111")

    def test_sin_recibos_asociados(self):
        frappe_mock = self._mock_frappe(receipts=[])
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

    def test_se_define_lista_para_registro_cuando_total_recibos_igual_a_factura(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            receipts=[
                {"name": "REC1:9001", "supplier_delivery_note": "REC1",
                 "posting_date": "2026-07-16", "total": 600},
                {"name": "REC2:9001", "supplier_delivery_note": "REC2",
                 "posting_date": "2026-07-17", "total": 400},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "V")
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "DOC1", "nvfac_esta", "V"
        )

    def test_no_cambia_estado_cuando_total_recibos_no_cubre_total(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            receipts=[
                {"name": "REC1:9001", "supplier_delivery_note": "REC1",
                 "posting_date": "2026-07-16", "total": 400},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "E")
        frappe_mock.db.set_value.assert_not_called()

    def test_no_registra_cuando_total_recibos_supera_factura(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            receipts=[
                {"name": "REC1:9001", "supplier_delivery_note": "REC1",
                 "posting_date": "2026-07-16", "total": 1200},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="E")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "E")
        frappe_mock.db.set_value.assert_not_called()

    def test_no_reescribe_estado_registrado(self):
        frappe_mock = self._mock_frappe(
            po_items=[],
            receipts=[
                {"name": "REC1:9001", "supplier_delivery_note": "REC1",
                 "posting_date": "2026-07-16", "total": 1000},
            ],
        )
        document = self._make_document(nvfac_orde="OC111", nvfac_totp=1000, nvfac_esta="A")
        self._run(document, frappe_mock)

        self.assertEqual(document["nvfac_esta"], "A")
        frappe_mock.db.set_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
