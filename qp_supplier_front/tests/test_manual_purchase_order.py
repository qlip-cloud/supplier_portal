# -*- coding: utf-8 -*-
"""
test_manual_purchase_order.py
=============================
Asignacion manual de la OC en facturas de credito sin OC
(resources/documenteme/purchase_order_reference.py).

Infraestructura con `frappe` mockeado: no requiere base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_manual_purchase_order -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import qp_supplier_front.resources.documenteme.purchase_order_reference as module


def _doc(**fields):
    base = {
        "name": "SUP:FC1",
        "nvfac_nume": "FC1",
        "nvpro_ndoc": "900",
        "nvtip_docu": "F",
        "nvfac_conv": "2",
        "nvfac_orde": "",
        "nvfac_esta": "SO",
        "document_sync_line": "FC1",
        "qp_manual_purchase_order": "",
    }
    base.update(fields)
    return base


class TestParseOrders(unittest.TestCase):

    def test_lista(self):
        self.assertEqual(module._parse_orders(["OC1", "OC2"]), ["OC1", "OC2"])

    def test_json(self):
        self.assertEqual(module._parse_orders('["OC1", "OC2"]'), ["OC1", "OC2"])

    def test_coma(self):
        self.assertEqual(module._parse_orders("OC1, OC2"), ["OC1", "OC2"])

    def test_vacio(self):
        self.assertEqual(module._parse_orders(""), [])


class TestValidateScope(unittest.TestCase):

    def test_credito_sin_oc_valido(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertEqual(module._validate_scope(_doc()), "")

    def test_contado(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertIn("credito", module._validate_scope(
                _doc(nvfac_conv="1")))

    def test_nota_credito(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertIn("notas de credito", module._validate_scope(
                _doc(nvtip_docu="C")))

    def test_servicio(self):
        with patch.object(module, "is_service_supplier_doc", return_value=True), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertIn("servicio", module._validate_scope(_doc()))

    def test_delivery(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: True):
            self.assertIn("delivery", module._validate_scope(_doc()))

    def test_estado_no_asignable(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertIn("pendiente", module._validate_scope(
                _doc(nvfac_esta="V")))

    def test_oc_del_origen_no_se_reemplaza(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertIn("origen", module._validate_scope(
                _doc(nvfac_orde="OC-ORIGEN")))

    def test_oc_manual_previa_se_puede_cambiar(self):
        with patch.object(module, "is_service_supplier_doc", return_value=False), \
             patch.object(module, "make_delivery_order_predicate",
                          return_value=lambda doc: False):
            self.assertEqual(module._validate_scope(_doc(
                nvfac_orde="OC-MANUAL",
                qp_manual_purchase_order="OC-MANUAL",
            )), "")


class TestGetCandidates(unittest.TestCase):

    def test_filtra_por_confirmacion_y_canceladas(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [
            {"name": "OC1", "supplier": "SUP", "transaction_date": "2026-01-01",
             "grand_total": 100, "qp_oc_type": "01", "qp_headquarter": "BOG",
             "qp_order_confirmation_no": "OC1", "status": "To Bill"},
            {"name": "OC2", "supplier": "SUP", "transaction_date": "2026-01-02",
             "grand_total": 200, "qp_oc_type": "01", "qp_headquarter": "BOG",
             "qp_order_confirmation_no": "OTRO", "status": "To Bill"},
            {"name": "OC3", "supplier": "SUP", "transaction_date": "2026-01-03",
             "grand_total": 300, "qp_oc_type": "01", "qp_headquarter": "BOG",
             "qp_order_confirmation_no": "OC3", "status": "Cancelled"},
        ]
        response_mock = MagicMock()

        with patch.object(module, "frappe", frappe_mock), \
             patch.object(module, "response", response_mock), \
             patch.object(module, "_has_permission", return_value=True), \
             patch.object(module, "_get_doc", return_value=_doc()), \
             patch.object(module, "_validate_scope", return_value=""), \
             patch.object(module, "get_supplier_by_tax_id", return_value="SUP"), \
             patch.object(module, "get_receipt_bank", return_value=[]):
            module.get_purchase_order_candidates("SUP:FC1")

        args, _kwargs = response_mock.call_args
        self.assertEqual(args[0], 200)
        orders = args[2]["orders"]
        self.assertEqual([row["name"] for row in orders], ["OC1"])

    def test_incluye_ordenes_en_borrador(self):
        """Las POs sincronizadas sin submitir tambien son candidatas."""
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [
            {"name": "OC1", "supplier": "SUP", "transaction_date": "2026-01-01",
             "grand_total": 100, "qp_oc_type": "01", "qp_headquarter": "BOG",
             "qp_order_confirmation_no": "OC1", "status": "Draft"},
        ]
        response_mock = MagicMock()

        with patch.object(module, "frappe", frappe_mock), \
             patch.object(module, "response", response_mock), \
             patch.object(module, "_has_permission", return_value=True), \
             patch.object(module, "_get_doc", return_value=_doc()), \
             patch.object(module, "_validate_scope", return_value=""), \
             patch.object(module, "get_supplier_by_tax_id", return_value="SUP"), \
             patch.object(module, "get_receipt_bank", return_value=[]):
            module.get_purchase_order_candidates("SUP:FC1")

        filters = frappe_mock.get_all.call_args[1]["filters"]
        self.assertEqual(filters["docstatus"], ["<", 2])
        self.assertEqual(response_mock.call_args[0][2]["orders"][0]["name"], "OC1")

    def test_sin_permiso(self):
        response_mock = MagicMock()
        with patch.object(module, "frappe", MagicMock()), \
             patch.object(module, "response", response_mock), \
             patch.object(module, "_has_permission", return_value=False):
            module.get_purchase_order_candidates("SUP:FC1")
        self.assertEqual(response_mock.call_args[0][0], 403)


class TestAssignPurchaseOrder(unittest.TestCase):

    def _run(self, doc=None, orders="OC1", approve="false",
             po_supplier=True, oc_context=True, reassign=None,
             approve_core=None):
        frappe_mock = MagicMock()
        frappe_mock.get_doc.return_value = doc or _doc()
        frappe_mock.session.user = "u@x.com"
        frappe_mock.utils.now.return_value = "2026-11-17 10:00:00"
        response_mock = MagicMock()
        timeline = MagicMock()
        reassign = reassign if reassign is not None else {
            "reassigned": True, "previous": ["a@x.com"], "users": ["b@x.com"]}
        approve_core = approve_core or MagicMock(return_value={"ok": True})

        patches = [
            patch.object(module, "frappe", frappe_mock),
            patch.object(module, "response", response_mock),
            patch.object(module, "_has_permission", return_value=True),
            patch.object(module, "_validate_scope", return_value=""),
            patch.object(module, "po_exists", return_value=True),
            patch.object(module, "po_supplier_match",
                         return_value=po_supplier),
            patch.object(module, "get_oc_context",
                         return_value={"oc_type": "01",
                                       "headquarter": "BOG"} if oc_context else None),
            patch.object(module, "reassign_to_oc_group",
                         return_value=reassign),
            patch.object(module, "run_auto_assign"),
            patch.object(module, "run_auto_approve"),
            patch.object(module, "run_auto_reject"),
            patch.object(module, "approve_documents_core", approve_core),
            patch.object(module, "resolve_backend", return_value="BC"),
            patch("qp_supplier_front.infrastructure.adapters.timeline_adapter.RealTimelineAdapter",
                  return_value=timeline),
        ]
        for item in patches:
            item.start()
        try:
            module.assign_purchase_order("SUP:FC1", orders, approve=approve)
        finally:
            for item in reversed(patches):
                item.stop()

        return frappe_mock, response_mock, timeline, approve_core

    def test_persiste_y_dispara_flujo(self):
        frappe_mock, response_mock, timeline, _ = self._run()
        values = frappe_mock.db.set_value.call_args[0][2]
        self.assertEqual(values["qp_manual_purchase_order"], "OC1")
        self.assertEqual(values["nvfac_orde"], "OC1")
        self.assertEqual(values["nvfac_esta"], "E")
        self.assertEqual(values["qp_manual_po_assigned_by"], "u@x.com")
        timeline.add_comment.assert_called_once()
        self.assertEqual(response_mock.call_args[0][0], 200)

    def test_multi_oc(self):
        frappe_mock, response_mock, timeline, _ = self._run(
            orders='["OC1", "OC2"]')
        values = frappe_mock.db.set_value.call_args[0][2]
        self.assertEqual(values["qp_manual_purchase_order"], "OC1, OC2")

    def test_oc_de_otro_proveedor_rechaza(self):
        frappe_mock, response_mock, timeline, _ = self._run(
            po_supplier=False)
        self.assertEqual(response_mock.call_args[0][0], 400)
        frappe_mock.db.set_value.assert_not_called()
        timeline.add_comment.assert_not_called()

    def test_asignar_y_aprobar(self):
        _, response_mock, _, approve_core = self._run(approve="true")
        approve_core.assert_called_once()
        self.assertEqual(response_mock.call_args[0][0], 200)

    def test_sin_grupo_conserva_asignados(self):
        _, response_mock, timeline, _ = self._run(
            reassign={"reassigned": False, "reason": "sin_grupo"})
        message = timeline.add_comment.call_args[0][1]
        self.assertIn("conservan los asignados", message)
        self.assertEqual(response_mock.call_args[0][0], 200)


if __name__ == "__main__":
    unittest.main()
