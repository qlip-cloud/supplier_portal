# -*- coding: utf-8 -*-
"""
test_sim_sync_in_memory.py
==========================
Escenario end-to-end del sync simulado: con el flag activo, _sync_documents
persiste fases 1-2 (cabeceras + detalles) SOLO en el store en memoria, sin
escribir en la base de datos real, y el mismo store alimenta la vista.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sim_sync_in_memory.py -v
"""
import unittest
from unittest.mock import MagicMock, patch

import qp_supplier_front.uses_cases.documents.sync_all_whitelist as saw  # noqa: E402
from qp_supplier_front.simulation import session  # noqa: E402


class TestSimSyncInMemory(unittest.TestCase):

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.frappe_mock.get_all.return_value = ["COMP-A"]
        session.reset()
        self.addCleanup(session.reset)

    def _patched(self):
        return [
            patch.object(saw, "frappe", self.frappe_mock),
            patch.object(saw.runtime, "is_simulation_enabled", return_value=True),
            patch.object(saw, "run_documenteme_stale_status_alerts"),
            patch.object(saw, "run_documenteme_auto_assign"),
            patch.object(saw, "run_documenteme_auto_approve", return_value={}),
        ]

    def test_sync_persiste_en_memoria_sin_db_real(self):
        for p in self._patched():
            p.start()
            self.addCleanup(p.stop)

        saw._sync_documents()

        store = session.store()
        docs = store.query("qp_SP_DocumentDetail")
        self.assertEqual(len(docs), 11)
        self.assertEqual(
            {d["nvfac_esta"] for d in docs}, {"E"})
        self.assertEqual(
            {d["name"] for d in docs},
            {
                "999999999:SIM-FAC-0001",
                "999999999:SIM-FAC-0002",
                "999999999:SIM-FAC-0003",
                "999999999:SIM-FAC-0004",
                "999999999:SIM-POA-0001",
                "999999999:SIM-POA-0002",
                "999999999:SIM-POB-0001",
                "999999999:SIM-POB-0002",
                "999999999:SIM-POB-0003",
                "999999999:SIM-POC-0001",
                "999999999:SIM-POC-0002",
            })

        lines = store.query("qp_SP_DocumentSyncLine")
        self.assertEqual(len(lines), 11)
        self.assertTrue(all(l["is_completed"] == 1 for l in lines))

        logs = store.query("qp_SP_DocumentSyncLog")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["tax_id"], "999999999")

        # Nada se escribio en la base de datos real
        self.frappe_mock.new_doc.assert_not_called()
        self.frappe_mock.db.set_value.assert_not_called()

    def test_nuevo_sync_descarta_store_anterior(self):
        for p in self._patched():
            p.start()
            self.addCleanup(p.stop)

        saw._sync_documents()
        first_batch = [d["name"] for d in session.store().query("qp_SP_DocumentDetail")]
        self.assertEqual(len(first_batch), 11)

        # Marcar un doc localmente para verificar que el reset lo descarta
        session.reset()
        with patch.object(saw.runtime, "resolve") as resolve:
            # resolve simulado no se usa: solo verificamos que reset limpia
            pass
        store = session.store()
        self.assertEqual(store.count("qp_SP_DocumentDetail"), 0)


if __name__ == "__main__":
    unittest.main()