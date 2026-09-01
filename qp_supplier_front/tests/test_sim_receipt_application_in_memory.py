# -*- coding: utf-8 -*-
"""
test_sim_receipt_application_in_memory.py
===========================================
Seleccion manual del banco de recepciones EN MEMORIA (modo simulador):
ejerce el recurso whitelist (apply/get_bank) contra el bundle simulado de
runtime (callbacks de memoria + confirmacion simulada), sin base de datos.

Cubre:
- parcial: reclamar RESERVA los recibos (qp_invoice seteado) sin iniciar
  aprobacion (la factura sigue no definitiva).
- completo: reclamar + iniciar aprobacion -> BCC -> confirmacion simulada
  (030/032/033) -> A; los recibos quedan consumidos.
- liberar todo: aplicar sin seleccion libera los recibos de vuelta al pool.
- exclusion: los recibos reclamados por una factura NO aparecen en el banco
  de otra factura de la misma OC.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_receipt_application_in_memory -v
"""
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe"].whitelist = lambda *a, **k: (lambda fn: fn)
sys.modules["frappe"].parse_json = lambda v: (
    json.loads(v) if isinstance(v, str) else v
)

from qp_supplier_front.resources.documenteme import receipt_selection as infra  # noqa: E402
from qp_supplier_front.resources.documenteme import runtime  # noqa: E402
from qp_supplier_front.simulation import seeds, session  # noqa: E402


def _doc(name, nvfac_nume, nvfac_orde, nvfac_stot):
    return {
        "name": name,
        "document_sync_line": name,
        "nvfac_nume": nvfac_nume,
        "nvpro_ndoc": seeds.SIM_NIT,
        "nvfac_fech": "2026-08-10 10:00:00",
        "nvfac_cufe": "",
        "nvtip_docu": "F",
        "nvfac_fpag": "",
        "nvfac_orde": nvfac_orde,
        "nvfac_rece": "",
        "nvfac_totp": int(nvfac_stot * 1.19),
        "nvfac_esta": "E",
        "nvfac_ueve": "",
        "nvfac_conv": "2",
        "nvmon_codi": "COP",
        "nvfac_stot": nvfac_stot,
        "nvfac_viva": 0,
        "nvpro_nomb": "Proveedor Sim",
        "nvfac_cont": "CONT-1",
    }


class TestSimReceiptApplication(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.addCleanup(session.reset)
        self.store = session.store()
        sys.modules["frappe"].response = {}
        seeds.seed_scenario(self.store)
        # Factura manual de credito sobre PO-A-0001 (banco A: 500, 1500, 1000, 3000)
        self.store.insert("qp_SP_DocumentDetail", _doc(
            "SIM:PO-MANUAL-0001", "PO-MANUAL-0001", "PO-A-0001", 2000))
        self.store.insert("qp_SP_DocumentDetail", _doc(
            "SIM:OFRA-IN-0001", "OFRA-IN-0001", "PO-A-0001", 4000))

        self.bundle = runtime._simulated_bundle()
        self.patches = [
            patch.object(runtime, "resolve", lambda: self.bundle),
            patch.object(infra, "_has_permission", lambda roles: True),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def _msg(self):
        return sys.modules["frappe"].response["message"]

    def _receipt(self, name):
        return self.store.query(
            "qp_SP_PurchaseReceipt", filters={"name": name}, limit=1)[0]

    def test_parcial_reserva_sin_aprobar(self):
        infra.apply("SIM:PO-MANUAL-0001", '["REC-A-1"]')
        message = self._msg()
        self.assertEqual(message["status"], 200)
        self.assertIn("no cubre", message["msg"])
        # Recibo reclamado pero factura NO definitiva (no se aprobo).
        self.assertEqual(self._receipt("REC-A-1")["qp_invoice"], "PO-MANUAL-0001")
        doc = self.store.get("qp_SP_DocumentDetail", "SIM:PO-MANUAL-0001")
        self.assertEqual(doc["nvfac_esta"], "E")

    def test_completo_aprueba_y_consume(self):
        infra.apply("SIM:PO-MANUAL-0001", '["REC-A-1"]')
        infra.apply("SIM:PO-MANUAL-0001", '["REC-A-1", "REC-A-2"]')
        message = self._msg()
        self.assertEqual(message["status"], 200)
        self.assertIn("aprobando", message["msg"])
        # Credit: BCC -> confirmacion simulada 030/032/033 -> A.
        doc = self.store.get("qp_SP_DocumentDetail", "SIM:PO-MANUAL-0001")
        self.assertEqual(doc["nvfac_esta"], "A")
        self.assertEqual(doc["nvfac_ueve"], "033")
        self.assertEqual(self._receipt("REC-A-1")["qp_invoice"], "PO-MANUAL-0001")
        self.assertEqual(self._receipt("REC-A-2")["qp_invoice"], "PO-MANUAL-0001")
        # REC-A-3/4 siguen libres.
        self.assertFalse(self._receipt("REC-A-3")["qp_invoice"])
        self.assertFalse(self._receipt("REC-A-4")["qp_invoice"])

    def test_sin_seleccion_libera_todo(self):
        infra.apply("SIM:PO-MANUAL-0001", '["REC-A-1"]')
        infra.apply("SIM:PO-MANUAL-0001", '[]')
        message = self._msg()
        self.assertEqual(message["status"], 200)
        self.assertIn("liberaron", message["msg"])
        self.assertFalse(self._receipt("REC-A-1")["qp_invoice"])

    def test_recibos_reclamados_invisibles_en_otra_factura(self):
        infra.apply("SIM:PO-MANUAL-0001", '["REC-A-1", "REC-A-2"]')
        infra.get_bank("SIM:OFRA-IN-0001")
        data = self._msg()["data"]
        names = [row["name"] for row in data["receipts"]]
        self.assertNotIn("REC-A-1", names)
        self.assertNotIn("REC-A-2", names)
        self.assertIn("REC-A-3", names)
        self.assertIn("REC-A-4", names)

    def test_vista_banco_muestra_reclamados_por_factura(self):
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        from qp_supplier_front.services.enrich_document_list import enrich_document_list

        infra.apply("SIM:PO-MANUAL-0001", '["REC-A-1"]')
        doc = self.store.get("qp_SP_DocumentDetail", "SIM:PO-MANUAL-0001")
        facade = DataFacade(store=self.store)
        enrich_document_list([doc], "qp_SP_DocumentDetail", data=facade)
        bank = {row["name"]: row for row in doc["banco_recepciones"]}
        self.assertTrue(bank["REC-A-1"]["claimed_by_me"])
        self.assertTrue(bank["REC-A-1"]["selectable"])
        self.assertFalse(doc["hide_unselected_recibos"])


if __name__ == "__main__":
    unittest.main()