# -*- coding: utf-8 -*-
"""
test_receipt_bank_gates.py
==========================
Pruebas de los gates de la seleccion manual del banco de recepciones:

1. auto_approve: las facturas con recibos reclamados manualmente se excluyen
   de promote/candidatos (manual excluye auto).
2. enrich_document_detail: banco_recepciones (checkbox) se puebla para estado
   no definitivo y solo muestra los vinculados en estado definitivo.

Frappe se inyecta como mock en sys.modules.
Ejecutar cada archivo por separado (flakes de fragge=MagicMock() entre tests).
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe"].whitelist = lambda *a, **k: (lambda fn: fn)

from qp_supplier_front.resources.documenteme import auto_approve as infra  # noqa: E402
from qp_supplier_front.services.enrich_document_detail import (  # noqa: E402
    enrich_document_detail,
)


def _doc(name="DOC1", nvfac_nume="FAC1", nvfac_esta="E", nvfac_orde="PO1",
         nvfac_conv="2", nvfac_stot=100):
    return {
        "name": name,
        "nvfac_nume": nvfac_nume,
        "nvfac_orde": nvfac_orde,
        "nvfac_totp": 119,
        "nvfac_stot": nvfac_stot,
        "nvfac_esta": nvfac_esta,
        "nvfac_ueve": None,
        "nvfac_conv": nvfac_conv,
    }


class TestAutoApproveGate(unittest.TestCase):

    def _ctx(self, docs, claimed):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = docs
        bundle = {
            "data": None,
            "claimed_invoice_numbers_fn": lambda: set(claimed),
        }
        patches = [
            patch.object(infra, "frappe", frappe_mock),
            patch.object(infra.runtime, "resolve", lambda: bundle),
        ]
        start = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        return frappe_mock

    def test_candidatos_excluyen_facturas_con_reclamos(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC1"),
            _doc(name="DOC2", nvfac_nume="FAC2"),
        ]
        self._ctx(docs, claimed={"FAC2"})
        candidates = infra.get_analysis_candidates()
        nums = [doc.get("nvfac_nume") for doc in candidates]
        self.assertEqual(nums, ["FAC1"])

    def test_sin_reclamos_ninguno_se_excluye(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC1")]
        self._ctx(docs, claimed=set())
        candidates = infra.get_analysis_candidates()
        self.assertEqual([doc.get("nvfac_nume") for doc in candidates], ["FAC1"])

    def test_v_docs_excluyen_facturas_con_reclamos(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC1", nvfac_esta="V"),
            _doc(name="DOC2", nvfac_nume="FAC2", nvfac_esta="V"),
        ]
        self._ctx(docs, claimed={"FAC2"})
        names = infra.get_v_doc_names()
        self.assertEqual(names, ["DOC1"])


class _FakeRefs(object):

    def po_exists(self, purchase_order):
        return True

    def po_items(self, purchase_order):
        return []

    def receipts_for(self, purchase_order, qp_invoice=None):
        if qp_invoice == "FAC1":
            return [{
                "name": "R1", "supplier_delivery_note": "R1",
                "posting_date": "2026-01-01", "total": 100,
            }]
        return []

    def receipt_bank_for(self, purchase_order):
        return [
            {"name": "R1", "amount": 100, "date": "2026-01-01",
             "qp_invoice": "FAC1"},
            {"name": "R2", "amount": 50, "date": "2026-01-01",
             "qp_invoice": None},
        ]

    def bank_for_invoice(self, purchase_order, invoice_number):
        return [
            {"name": "R2", "amount": 50, "date": "2026-01-01",
             "qp_invoice": None, "claimed_by_me": False, "selectable": True},
        ]

    def has_claimed_receipts(self, invoice_number):
        return False

    def receipt_items_for(self, receipt_names):
        return []


class TestEnrichReceiptBank(unittest.TestCase):

    def _ctx(self, doc):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        patch_obj = patch.dict(sys.modules, {"frappe": frappe_mock})
        patch_obj.start()
        self.addCleanup(patch_obj.stop)
        return frappe_mock

    def test_estado_no_definitivo_muestra_banco_seleccionable(self):
        doc = _doc(nvfac_esta="E")
        self._ctx(doc)
        enrich_document_detail(doc, references=_FakeRefs())
        self.assertFalse(doc["hide_unselected_recibos"])
        self.assertEqual(
            [r["name"] for r in doc["banco_recepciones"]], ["R2"])
        self.assertTrue(doc["banco_recepciones"][0]["selectable"])

    def test_estado_no_definitivo_no_promueve_a_v_con_reclamo(self):
        doc = _doc(nvfac_esta="E")
        self._ctx(doc)
        enrich_document_detail(doc, references=_FakeRefs())
        # R1 esta reclamada por FAC1 -> la factura no se promueve a V
        self.assertEqual(doc["nvfac_esta"], "E")

    def test_estado_definitivo_solo_recibos_vinculados(self):
        doc = _doc(nvfac_esta="BCC")
        self._ctx(doc)
        enrich_document_detail(doc, references=_FakeRefs())
        self.assertTrue(doc["hide_unselected_recibos"])
        self.assertEqual(
            [r["name"] for r in doc["banco_recepciones"]], ["R1"])
        self.assertFalse(doc["banco_recepciones"][0]["selectable"])


if __name__ == "__main__":
    unittest.main()