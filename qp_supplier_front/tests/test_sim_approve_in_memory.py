# -*- coding: utf-8 -*-
"""
test_sim_approve_in_memory.py
=============================
Aprobacion simulada 100% en memoria: con el flag activo, approve_documents_core
usa callbacks memory (get_docs/persist/mark/refs) sobre el store de la sesion;
contado llega a "A" y credito sin OC queda en error (sin tocar DB real).

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sim_approve_in_memory.py -v
"""
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.resources.documenteme import _approve_base
from qp_supplier_front.resources.documenteme import simulation as doc_sim
from qp_supplier_front.simulation import session
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


def _seed_cash(store, name="999999999:F2", nume="SIM-FAC-0002", total=800000):
    store.insert("qp_SP_Supplier", {"name": SIM_NIT, "tax_id": SIM_NIT})
    store.insert("qp_SP_PurchaseOrder", {
        "name": "PO-SIM-0002", "supplier": "999999999",
        "qp_headquarter": "HQ01",
    })
    store.insert("qp_SP_PurchaseOrderItem", {
        "name": "PO-SIM-0002:ITEM-2", "parent": "PO-SIM-0002",
        "parenttype": "Purchase Order", "item_code": "ITEM-2",
        "qty": 2, "rate": 400000, "idx": 0, "uom": "UND",
    })
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": nume, "nvpro_ndoc": SIM_NIT,
        "nvfac_fech": "2026-08-25", "nvfac_cufe": "CUFE2",
        "nvtip_docu": "FAC", "nvfac_fpag": "", "nvfac_orde": "PO-SIM-0002",
        "nvfac_rece": "", "nvfac_totp": total, "nvfac_esta": "V",
        "nvfac_ueve": "", "nvfac_conv": "1", "nvmon_codi": "COP",
        "nvfac_stot": total, "nvfac_viva": 0, "nvpro_nomb": "PROVEEDOR SIM",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": name, "nvpro_codi": "ITEM-2", "nvdet_tcan": 2,
        "nvdet_valo": 400000, "nvdet_stot": total,
    })


def _seed_home_delivery(store):
    store.insert("qp_SP_MasterSetup", {
        "name": "qp_SP_MasterSetup",
        "documenteme_backend": "BC",
    })
    store.insert("qp_SP_DeliveryType", {
        "name": "home_delivery",
        "title": "Home delivery",
        "code": "entregapaciente009",
        "description": "Factura de home delivery",
    })
    store.insert("qp_SP_DeliveryItem", {
        "parent": "qp_SP_MasterSetup",
        "parentfield": "delivery_items",
        "delivery_type": "home_delivery",
        "item_code": "HD-ITEM",
    })
    store.insert("qp_SP_DocumentDetail", {
        "name": "999999999:HD", "nvfac_nume": "SIM-FAC-HD",
        "nvpro_ndoc": SIM_NIT, "nvfac_fech": "2026-08-25",
        "nvfac_cufe": "CUFEHD", "nvtip_docu": "FAC", "nvfac_fpag": "",
        "nvfac_orde": "ENTREGAPACIENTE009", "nvfac_rece": "",
        "nvfac_totp": 350000, "nvfac_esta": "V", "nvfac_ueve": "",
        "nvfac_conv": "1", "nvmon_codi": "COP", "nvfac_stot": 350000,
        "nvfac_viva": 0, "nvpro_nomb": "PROVEEDOR SIM",
    })
    for idx, (qty, unit, subtotal) in enumerate((
            (2, 100000, 200000), (3, 50000, 150000))):
        store.insert("qp_SP_DetailLine", {
            "parent": "999999999:HD", "nvpro_codi": "ITEM-{}".format(idx),
            "nvdet_tcan": qty, "nvdet_valo": unit, "nvdet_stot": subtotal,
        })


def _seed_internal_delivery(store, supplier_item=None, master_item=None):
    store.insert("qp_SP_MasterSetup", {
        "name": "qp_SP_MasterSetup",
        "documenteme_backend": "BC",
    })
    store.insert("qp_SP_Supplier", {"name": SIM_NIT, "tax_id": SIM_NIT})
    store.insert("qp_SP_DeliveryType", {
        "name": "internal_delivery",
        "title": "Internal delivery",
        "code": "entregainterna009",
        "description": "Factura de internal delivery",
    })
    if supplier_item:
        store.insert("qp_SP_DeliveryItem", {
            "parent": SIM_NIT,
            "parentfield": "qp_delivery_items",
            "delivery_type": "internal_delivery",
            "item_code": supplier_item,
        })
    if master_item:
        store.insert("qp_SP_DeliveryItem", {
            "parent": "qp_SP_MasterSetup",
            "parentfield": "delivery_items",
            "delivery_type": "internal_delivery",
            "item_code": master_item,
        })
    store.insert("qp_SP_DocumentDetail", {
        "name": "999999999:ID", "nvfac_nume": "SIM-FAC-ID",
        "nvpro_ndoc": SIM_NIT, "nvfac_fech": "2026-08-25",
        "nvfac_cufe": "CUFEID", "nvtip_docu": "FAC", "nvfac_fpag": "",
        "nvfac_orde": "ENTREGAINTERNA009", "nvfac_rece": "",
        "nvfac_totp": 100000, "nvfac_esta": "V", "nvfac_ueve": "",
        "nvfac_conv": "1", "nvmon_codi": "COP", "nvfac_stot": 100000,
        "nvfac_viva": 0, "nvpro_nomb": "PROVEEDOR SIM",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": "999999999:ID", "nvpro_codi": "ITEM-1",
        "nvdet_tcan": 2, "nvdet_valo": 50000, "nvdet_stot": 100000,
    })


def _seed_credit(store, name="999999999:F1", nume="SIM-FAC-0001", total=1500000):
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": nume, "nvpro_ndoc": SIM_NIT,
        "nvfac_fech": "2026-08-25", "nvfac_cufe": "CUFE1",
        "nvtip_docu": "FAC", "nvfac_fpag": "", "nvfac_orde": "PO-SIM-0001",
        "nvfac_rece": "", "nvfac_totp": total, "nvfac_esta": "V",
        "nvfac_ueve": "", "nvfac_conv": "2", "nvmon_codi": "COP",
        "nvfac_stot": total, "nvfac_viva": 0, "nvpro_nomb": "PROVEEDOR SIM",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": name, "nvpro_codi": "ITEM-1", "nvdet_tcan": 10,
        "nvdet_valo": 150000, "nvdet_stot": total,
    })


class TestSimApproveInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        self.addCleanup(session.reset)

    def _run(self, doc_names):
        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()):
            return _approve_base.approve_documents_core(doc_names)

    def test_contado_llega_a_aprobado(self):
        _seed_cash(self.store)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            self._run(["999999999:F2"])

        row = self.store.get("qp_SP_DocumentDetail", "999999999:F2")
        self.assertEqual(row["nvfac_esta"], "A")
        self.assertTrue(self.store.exists("qp_SP_PurchaseInvoice", "999999999:F2"))
        inv = self.store.query("qp_SP_PurchaseInvoice")
        self.assertEqual(inv[0]["invoice_id"], "SIMSIM-FAC-0002")
        bc = self.store.query("qp_SP_PurchaseInvoiceBC")
        self.assertEqual(len(bc), 1)

    def test_credito_sin_oc_queda_en_error(self):
        _seed_credit(self.store)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = self._run(["999999999:F1"])

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        row = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertNotEqual(row["nvfac_esta"], "A")

    def test_home_delivery_envia_una_linea_con_producto_configurado(self):
        _seed_home_delivery(self.store)
        captured = {}

        def fake_send(endpoint_code=None, payload=None):
            captured["payload"] = payload
            return {
                "Result": 0,
                "invoices": [{"doc_number": "SIM-HD", "error": ""}],
            }, 200

        with patch.object(doc_sim, "send_purchase_invoice_request", fake_send), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = self._run(["999999999:HD"])

        self.assertEqual(len(result["approved"]), 1)
        invoice = captured["payload"][0]
        self.assertEqual(invoice["NoPedidoProveedor"], "")
        self.assertEqual(len(invoice["vendorInvoiceLine"]), 1)
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["NoProducto"], "HD-ITEM")
        self.assertEqual(line["cantidad"], 5)
        self.assertEqual(line["Precio"], 70000)
        self.assertEqual(line["NoPedido"], "")
        self.assertIn("Factura de home delivery", line["Comentarios"])

    def test_internal_delivery_prioriza_producto_del_proveedor(self):
        _seed_internal_delivery(
            self.store,
            supplier_item="SUP-INT",
            master_item="MASTER-INT",
        )
        captured = {}

        def fake_send(endpoint_code=None, payload=None):
            captured["payload"] = payload
            return {
                "Result": 0,
                "invoices": [{"doc_number": "SIM-ID", "error": ""}],
            }, 200

        with patch.object(doc_sim, "send_purchase_invoice_request", fake_send), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = self._run(["999999999:ID"])

        self.assertEqual(len(result["approved"]), 1)
        invoice = captured["payload"][0]
        self.assertEqual(invoice["NoPedidoProveedor"], "")
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["NoProducto"], "SUP-INT")
        self.assertIn("Factura de internal delivery", line["Comentarios"])

    def test_delivery_sin_producto_configurado_deja_error_explicito(self):
        _seed_internal_delivery(self.store)

        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = self._run(["999999999:ID"])

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn(
            "No hay producto configurado para el tipo de delivery",
            result["errors"][0]["error"],
        )


if __name__ == "__main__":
    unittest.main()