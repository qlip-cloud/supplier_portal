# -*- coding: utf-8 -*-
"""
test_event_dispatch.py
======================
Pruebas del dispatcher de eventos documenteme (event_dispatch.py):
consulta de vencidos, tope por tick y encolado con lock por documento.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_event_dispatch.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()

from qp_supplier_front.resources.documenteme import event_dispatch as mod  # noqa: E402


class TestGetDueEvents(unittest.TestCase):

    def test_consulta_vencidos_con_tope(self):
        frappe_mock = MagicMock()
        frappe_mock.db.sql.side_effect = [
            [{"name": "A"}, {"name": "B"}],
            [],
        ]
        with patch.object(mod, "frappe", frappe_mock):
            names = mod.get_due_events(limit=7)

        self.assertEqual(names, ["A", "B"])
        first_call = frappe_mock.db.sql.call_args_list[0]
        query, params = first_call[0][0], first_call[0][1]
        self.assertIn("qp_SP_DocumentDetail", query)
        self.assertIn("qp_event_next_at <= %(now)s", query)
        self.assertNotIn("IS NULL", query)
        self.assertEqual(params["limit"], 7)
        self.assertEqual(params["states"], ["PR", "PA"])

    def test_consulta_nulos_como_respaldo(self):
        frappe_mock = MagicMock()
        frappe_mock.db.sql.side_effect = [
            [{"name": "A"}],
            [{"name": "LEGACY"}],
        ]
        with patch.object(mod, "frappe", frappe_mock):
            names = mod.get_due_events(limit=7)

        self.assertEqual(names, ["A", "LEGACY"])
        second_query = frappe_mock.db.sql.call_args_list[1][0][0]
        self.assertIn("qp_event_next_at IS NULL", second_query)


class TestDispatchPendingEvents(unittest.TestCase):

    def test_encola_vencidos_con_lock(self):
        frappe_mock = MagicMock()
        lock_calls = []

        def acquire(domain, ttl=None):
            lock_calls.append(domain)
            return {"token": "t"} if domain.endswith(":A") else None

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "get_due_events", return_value=["A", "B"]), \
             patch.object(mod, "sync_lock") as lock_mock, \
             patch.object(mod, "_is_simulation_enabled", return_value=False):
            lock_mock.acquire.side_effect = acquire
            result = mod.dispatch_pending_events()

        self.assertEqual(result, ["A"])
        frappe_mock.enqueue.assert_called_once()
        kwargs = frappe_mock.enqueue.call_args[1]
        self.assertEqual(kwargs["doc_name"], "A")
        self.assertEqual(kwargs["lock_token"], "t")
        # B no se encola porque su lock estaba tomado.
        self.assertEqual(len(lock_calls), 2)

    def test_modo_simulacion_no_hace_nada(self):
        frappe_mock = MagicMock()
        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "_is_simulation_enabled", return_value=True):
            result = mod.dispatch_pending_events()
        self.assertEqual(result, [])
        frappe_mock.enqueue.assert_not_called()

    def test_fallo_de_encolado_libera_lock(self):
        frappe_mock = MagicMock()
        frappe_mock.enqueue.side_effect = Exception("boom")
        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "get_due_events", return_value=["A"]), \
             patch.object(mod, "sync_lock") as lock_mock, \
             patch.object(mod, "_is_simulation_enabled", return_value=False):
            lock_mock.acquire.return_value = {"token": "t"}
            result = mod.dispatch_pending_events()

        self.assertEqual(result, [])
        lock_mock.release.assert_called_once_with("documenteme_event:A", "t")


if __name__ == "__main__":
    unittest.main()
