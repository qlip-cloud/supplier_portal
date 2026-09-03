# -*- coding: utf-8 -*-
"""
test_receipt_selection_resource.py
==================================
Pruebas del recurso whitelist de seleccion manual del banco:
resources/documenteme/receipt_selection.py (get_bank / apply).

Frappe se inyecta como mock en sys.modules; el bundle de runtime se ofrece
con callbacks simulados para bank/claim/release.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_receipt_selection_resource.py -v
"""
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# @frappe.whitelist() debe ser un decorador identidad para poder llamar a las
# funciones del recurso directamente (senon el mock lo convierte en MagicMock).
sys.modules["frappe"] = MagicMock()
sys.modules["frappe"].whitelist = lambda *a, **k: (lambda fn: fn)
sys.modules["frappe"].parse_json = lambda value: (
    json.loads(value) if isinstance(value, str) else value
)

from qp_supplier_front.resources.documenteme import receipt_selection as infra  # noqa: E402


def _doc(nvfac_nume="FAC1", nvfac_stot=100, nvfac_esta="E", name="DOC1"):
    return {
        "name": name,
        "nvfac_nume": nvfac_nume,
        "nvfac_orde": "PO1",
        "nvfac_stot": nvfac_stot,
        "nvfac_esta": nvfac_esta,
        "nvfac_conv": "2",
    }


def _bank(rows):
    return [
        {
            "name": name,
            "amount": amount,
            "date": "2026-01-01",
            "qp_invoice": qp_invoice,
            "claimed_by_me": qp_invoice == "FAC1",
            "selectable": True,
        }
        for name, amount, qp_invoice in rows
    ]


def _bundle(bank, claim=None, release=None, data=None):
    return {
        "data": data,
        "receipt_bank_for_invoice_fn": lambda po, nume: bank,
        "claim_receipts_fn": claim or (lambda doc, names: []),
        "release_receipts_fn": release or (lambda doc, names: None),
        "has_claimed_receipts_fn": lambda nume: False,
        "claimed_invoice_numbers_fn": lambda: set(),
    }


class _Base(unittest.TestCase):

    def _setup(self, bank, claim=None, release=None, data=None, doc=None,
               approve=None, permission=True):
        frappe_mock = sys.modules["frappe"]
        frappe_mock.reset_mock()
        frappe_mock.response = {}
        frappe_mock.get_all.return_value = [doc or _doc()]
        bundle = _bundle(bank, claim=claim, release=release, data=data)
        patches = [
            patch.object(infra.runtime, "resolve", lambda: bundle),
            patch.object(infra, "_has_permission", lambda roles: permission),
        ]
        if approve is not None:
            patches.append(patch.object(
                infra, "run_approve_with_receipts", return_value=approve))
        start = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        return frappe_mock

    def _message(self, frappe_mock):
        return frappe_mock.response["message"]


class TestGetBank(_Base):

    def test_devuelve_banco_y_clasificacion(self):
        frappe_mock = self._setup(
            bank=_bank([("R1", 40, None), ("R2", 60, "FAC1")]))
        infra.get_bank("DOC1")
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 200)
        data = message["data"]
        self.assertEqual(data["stot"], 100)
        self.assertEqual(len(data["receipts"]), 2)
        self.assertEqual(data["classification"], "parcial")

    def test_sin_permisos_403(self):
        frappe_mock = self._setup(bank=[], permission=False)
        infra.get_bank("DOC1")
        self.assertEqual(self._message(frappe_mock)["status"], 403)


class TestApplyPartial(_Base):

    def test_reserva_sin_aprobar(self):
        claim_calls = []
        release_calls = []
        bank = _bank([("R1", 40, None), ("R2", 60, "FAC1")])
        frappe_mock = self._setup(
            bank=bank,
            claim=lambda doc, names: claim_calls.append((doc, names)) or [],
            release=lambda doc, names: release_calls.append((doc, names)),
        )
        infra.apply("DOC1", '["R2"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 200)
        self.assertIn("no cubre", message["msg"])
        self.assertEqual(message["data"]["classification"], "parcial")
        # R2 ya estaba reclamada por la factura -> no se re-reclama
        self.assertEqual(claim_calls, [])
        self.assertEqual(release_calls, [])

    def test_nuevo_recibo_parcial_se_reclama(self):
        claim_calls = []
        bank = _bank([("R1", 40, None), ("R2", 60, None)])
        frappe_mock = self._setup(
            bank=bank,
            claim=lambda doc, names: claim_calls.append(names) or [],
        )
        infra.apply("DOC1", '["R1"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 200)
        self.assertEqual(message["data"]["classification"], "parcial")
        self.assertEqual(claim_calls, [["R1"]])


class TestApplyComplete(_Base):

    def test_completo_dispara_aprobacion(self):
        bank = _bank([("R1", 40, None), ("R2", 60, None)])
        frappe_mock = self._setup(
            bank=bank,
            approve={
                "approved": [{"name": "DOC1", "nvfac_nume": "FAC1", "doc_number": "BC1"}],
                "errors": [],
            },
        )
        infra.apply("DOC1", '["R1","R2"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 200)
        self.assertIn("aprobando", message["msg"])
        infra.run_approve_with_receipts.assert_called_once()

    def test_error_de_aprobacion_devuelve_500(self):
        bank = _bank([("R1", 40, None), ("R2", 60, None)])
        frappe_mock = self._setup(
            bank=bank,
            approve={
                "approved": [],
                "errors": [{"nvfac_nume": "FAC1", "error": "BC fallo"}],
            },
        )
        infra.apply("DOC1", '["R1","R2"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 500)
        self.assertIn("BC fallo", message["msg"])


class TestApplyBlocks(_Base):

    def test_excede_no_reclama(self):
        claim_calls = []
        bank = _bank([("R1", 140, None)])
        frappe_mock = self._setup(
            bank=bank,
            claim=lambda doc, names: claim_calls.append(names) or [],
        )
        infra.apply("DOC1", '["R1"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 400)
        self.assertEqual(claim_calls, [])

    def test_estado_definitivo_bloquea(self):
        claim_calls = []
        bank = _bank([("R1", 40, None)])
        frappe_mock = self._setup(
            bank=bank,
            doc=_doc(nvfac_esta="BCC"),
            claim=lambda doc, names: claim_calls.append(names) or [],
        )
        infra.apply("DOC1", '["R1"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 400)
        self.assertIn("definitivo", message["msg"])
        self.assertEqual(claim_calls, [])

    def test_recibo_tomado_en_paralelo_409(self):
        bank = _bank([("R1", 40, None)])
        frappe_mock = self._setup(
            bank=bank,
            claim=lambda doc, names: ["R1"],
        )
        infra.apply("DOC1", '["R1"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 409)
        self.assertIn("otra factura", message["msg"])

    def test_sin_seleccion_bloquea(self):
        frappe_mock = self._setup(bank=_bank([("R1", 40, None)]))
        infra.apply("DOC1", '[]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 400)
        self.assertIn("al menos un recibo", message["msg"])

    def test_sin_permisos_403(self):
        frappe_mock = self._setup(bank=[], permission=False)
        infra.apply("DOC1", '["R1"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 403)


class TestApplyRelease(_Base):

    def test_desmarque_libera_recibo_previo(self):
        release_calls = []
        bank = _bank([("R1", 40, None), ("R2", 60, "FAC1")])
        frappe_mock = self._setup(
            bank=bank,
            release=lambda doc, names: release_calls.append(names),
        )
        # El usuario quita R2 (ya reclamada) y deja solo R1 (parcial nuevo)
        infra.apply("DOC1", '["R1"]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 200)
        self.assertEqual(message["data"]["classification"], "parcial")
        self.assertEqual(release_calls, [["R2"]])

    def test_sin_seleccion_libera_todos(self):
        release_calls = []
        claim_calls = []
        bank = _bank([("R1", 40, "FAC1"), ("R2", 60, "FAC1")])
        frappe_mock = self._setup(
            bank=bank,
            claim=lambda doc, names: claim_calls.append(names) or [],
            release=lambda doc, names: release_calls.append(names),
        )
        infra.apply("DOC1", '[]')
        message = self._message(frappe_mock)
        self.assertEqual(message["status"], 200)
        self.assertIn("liberaron", message["msg"])
        self.assertEqual(release_calls, [["R1", "R2"]])
        self.assertEqual(claim_calls, [])


if __name__ == "__main__":
    unittest.main()