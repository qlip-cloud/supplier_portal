# -*- coding: utf-8 -*-
"""
test_log_adapter.py
====================
Pruebas unitarias para infrastructure/adapters/log_adapter.py
(build_sync_log_fn: ciclo de vida create -> update).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_log_adapter -v
"""
import unittest
from unittest import mock

from qp_supplier_front.infrastructure.adapters import log_adapter


class TestBuildSyncLogFn(unittest.TestCase):

    def setUp(self):
        self.created = []
        self.updated = []

        self.log_sync_patch = mock.patch.object(
            log_adapter,
            "log_sync",
            side_effect=self._fake_log_sync,
        )
        self.update_patch = mock.patch.object(
            log_adapter,
            "update_sync_log",
            side_effect=self._fake_update,
        )
        self.log_sync_patch.start()
        self.update_patch.start()

    def tearDown(self):
        self.log_sync_patch.stop()
        self.update_patch.stop()

    def _fake_log_sync(self, **kwargs):
        name = "LOG-{}".format(len(self.created) + 1)
        self.created.append(kwargs)
        return name

    def _fake_update(self, name, **fields):
        self.updated.append((name, fields))
        return name

    def test_full_creates_in_progress_then_updates(self):
        log_fn = log_adapter.build_sync_log_fn(
            "Receipt", "SUP-1", "GP", "full", "2026-08-06"
        )
        log_fn("In Progress", "2026-01-01", "2026-01-31")
        log_fn("Success", "2026-01-01", "2026-01-31", records_inserted=5)

        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.created[0]["status"], "In Progress")
        self.assertEqual(len(self.updated), 1)
        self.assertEqual(self.updated[0][1]["status"], "Success")
        self.assertEqual(self.updated[0][1]["records_inserted"], 5)

    def test_full_error_updates_row(self):
        log_fn = log_adapter.build_sync_log_fn(
            "Receipt", "SUP-1", "GP", "full", "2026-08-06"
        )
        log_fn("In Progress", "2026-01-01", "2026-01-31")
        log_fn("Error", "2026-01-01", "2026-01-31", error_message="boom")

        self.assertEqual(len(self.created), 1)
        self.assertEqual(len(self.updated), 1)
        self.assertEqual(self.updated[0][1]["status"], "Error")
        self.assertEqual(self.updated[0][1]["error_message"], "boom")

    def test_incremental_skips_in_progress_and_creates_final_row(self):
        log_fn = log_adapter.build_sync_log_fn(
            "Receipt", "SUP-1", "GP", "incremental", "2026-08-06",
            track_in_progress=False,
        )
        log_fn("In Progress", "2026-01-01", "2026-01-31")
        log_fn("NoNewRecords", "2026-01-01", "2026-01-31", records_found=0)

        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.created[0]["status"], "NoNewRecords")
        self.assertEqual(len(self.updated), 0)

    def test_incremental_error_creates_error_row(self):
        log_fn = log_adapter.build_sync_log_fn(
            "Receipt", "SUP-1", "GP", "incremental", "2026-08-06",
            track_in_progress=False,
        )
        log_fn("In Progress", "2026-01-01", "2026-01-31")
        log_fn("Error", "2026-01-01", "2026-01-31", error_message="boom")

        self.assertEqual(len(self.created), 1)
        self.assertEqual(self.created[0]["status"], "Error")
        self.assertEqual(len(self.updated), 0)

    def test_returns_log_name(self):
        log_fn = log_adapter.build_sync_log_fn(
            "Order", "SUP-1", "GP", "full", "2026-08-06"
        )
        name = log_fn("In Progress", "2026-01-01", "2026-01-31")
        self.assertEqual(name, "LOG-1")


if __name__ == "__main__":
    unittest.main()
