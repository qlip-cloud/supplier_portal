# -*- coding: utf-8 -*-
"""
test_documenteme_fetch_guard.py
===============================
Guard de salida a produccion: `qp_SP_MasterSetup.documenteme_block_new_invoice_fetch`
bloquea SOLO la descarga de facturas nuevas (boton Actualizar y sync programado).
El resto del pipeline (alertas, asignacion, aprobacion, rechazo) sigue igual y la
carga manual por rango no se ve afectada.

Ejecutar con:
python -m unittest qp_supplier_front.tests.test_documenteme_fetch_guard -v
"""
import unittest
from unittest.mock import MagicMock, patch

import qp_supplier_front.uses_cases.documents.sync_all_whitelist as saw
from qp_supplier_front.infrastructure.adapters.master_setup_source import (
    RealMasterSetupSource,
    flag_enabled,
)


class TestFlagParsing(unittest.TestCase):

    def test_valores_validos(self):
        self.assertTrue(flag_enabled(1))
        self.assertTrue(flag_enabled(True))
        self.assertFalse(flag_enabled(0))
        self.assertFalse(flag_enabled(False))

    def test_valores_ilegibles_no_bloquean(self):
        self.assertFalse(flag_enabled(None))
        self.assertFalse(flag_enabled(MagicMock()))
        self.assertFalse(flag_enabled(""))

    def test_real_source_fail_open_si_la_columna_no_existe(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.side_effect = RuntimeError("no column")

        source = RealMasterSetupSource(frappe_module=frappe_mock)

        self.assertFalse(source.new_invoice_fetch_blocked())


class TestFetchGuardPipeline(unittest.TestCase):

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.frappe_mock.get_all.return_value = ["COMP-A"]
        self.sync_calls = []
        self.assign_calls = []
        self.approve_calls = []
        self.reject_calls = []
        self.alerts_calls = []

        self.patches = [
            patch.object(saw, "frappe", self.frappe_mock),
            patch.object(saw.runtime, "is_simulation_enabled", return_value=False),
            patch.object(saw.runtime, "resolve", return_value={
                "sync_send_fn": lambda *a, **k: ({}, 200),
                "sync_tax_id_fn": saw.get_company_tax_id,
                "sync_persist": {
                    "create_log": lambda *a, **k: "LOG",
                    "create_lines": lambda *a, **k: None,
                    "get_uncompleted_lines": lambda: [],
                    "get_log_company_tax_id": lambda *a, **k: None,
                    "create_document_detail": lambda *a, **k: None,
                    "log_sync_attempt": lambda *a, **k: None,
                    "mark_line_completed": lambda *a, **k: None,
                },
            }),
            patch.object(saw, "sync_by_supplier",
                         side_effect=lambda **kw: self.sync_calls.append(kw)),
            patch.object(saw, "sync_detail", return_value=["DOC-1"]),
            patch.object(saw, "run_documenteme_stale_status_alerts",
                         side_effect=lambda: self.alerts_calls.append(1)),
            patch.object(saw, "run_documenteme_auto_assign",
                         side_effect=lambda doc_names=None: self.assign_calls.append(doc_names)),
            patch.object(saw, "run_documenteme_auto_approve",
                         side_effect=lambda doc_names=None: (
                             self.approve_calls.append(doc_names)
                             or {"approved": [], "enqueued": 0})),
            patch.object(saw, "_launch_reject",
                         side_effect=lambda doc_names=None: (
                             self.reject_calls.append(doc_names)
                             or {"rejected": []})),
            patch.object(saw.sync_lock, "acquire", return_value={"token": "tok"}),
            patch.object(saw.sync_lock, "heartbeat", return_value=None),
            patch.object(saw.sync_lock, "release", return_value=None),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def _block_fetch(self, blocked=True):
        self.frappe_mock.db.get_single_value.return_value = 1 if blocked else 0

    def test_guard_abierto_descarga_normal(self):
        self._block_fetch(False)

        result = saw.refresh_documents()

        self.assertTrue(result["success"])
        self.assertFalse(result["fetch_blocked"])
        self.assertEqual([c["supplier_id"] for c in self.sync_calls], ["COMP-A"])
        self.assertEqual(result["created_count"], 1)

    def test_guard_cerrado_no_trae_facturas_pero_conserva_el_pipeline(self):
        self._block_fetch(True)

        result = saw.refresh_documents()

        self.assertTrue(result["success"])
        self.assertTrue(result["fetch_blocked"])
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(self.sync_calls, [])
        self.assertEqual(len(self.alerts_calls), 1)
        self.assertEqual(self.assign_calls, [[]])
        self.assertEqual(self.approve_calls, [[]])
        self.assertEqual(self.reject_calls, [[]])

    def test_by_date_range_bypassa_el_guard(self):
        self._block_fetch(True)

        result = saw.sync_by_date_range("2026-11-01", "2026-11-05")

        self.assertTrue(result["success"])
        self.assertFalse(result["fetch_blocked"])
        self.assertEqual([c["supplier_id"] for c in self.sync_calls], ["COMP-A"])
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(self.sync_calls[0]["nvfac_esta"], "T")
        self.assertEqual(self.sync_calls[0]["nvfac_fini"], "01/11/2026")
        self.assertEqual(self.sync_calls[0]["nvfac_ffin"], "05/11/2026")

    def test_guard_cerrado_y_lock_ocupado_responde_skipped(self):
        self._block_fetch(True)

        with patch.object(saw.sync_lock, "acquire", return_value=None):
            result = saw.refresh_documents()

        self.assertTrue(result["skipped"])
        self.assertEqual(self.sync_calls, [])

    def test_sync_all_es_noop_con_guard_cerrado(self):
        self._block_fetch(True)

        with patch.object(saw.sync_lock, "acquire") as acquire:
            result = saw.sync_all()

        self.assertTrue(result["success"])
        self.assertTrue(result["skipped"])
        self.assertTrue(result["fetch_blocked"])
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(self.sync_calls, [])
        self.assertEqual(self.alerts_calls, [])
        self.assertEqual(self.assign_calls, [])
        self.assertEqual(self.approve_calls, [])
        self.assertEqual(self.reject_calls, [])
        acquire.assert_not_called()

    def test_sync_all_corre_normal_con_guard_abierto(self):
        self._block_fetch(False)

        result = saw.sync_all()

        self.assertTrue(result["success"])
        self.assertFalse(result["fetch_blocked"])
        self.assertFalse(result.get("skipped") or False)
        self.assertEqual([c["supplier_id"] for c in self.sync_calls], ["COMP-A"])
        self.assertEqual(result["created_count"], 1)


if __name__ == "__main__":
    unittest.main()
