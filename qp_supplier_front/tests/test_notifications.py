# -*- coding: utf-8 -*-
"""
test_notifications.py
=====================
Pruebas del endpoint get_notifications (timeline de notificaciones del icono
de alerta) en modo real (frappe mockeado) y en memoria (facade del store).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_notifications -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
from qp_supplier_front.simulation.store import MemoryStore


def _make_frappe(event_logs=None, alerts=None, timeline_entries=None, doc_state="PA"):
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")
    utils.get_fullname = lambda user: "Admin Name" if user == "admin@example.com" else user
    frappe.utils = utils

    def _whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    frappe.whitelist = _whitelist
    frappe.session = MagicMock()
    frappe.session.user = "admin@example.com"
    frappe.db = MagicMock()
    frappe.db.get_value.return_value = doc_state
    frappe.db.rollback = MagicMock()
    frappe.generate_hash = MagicMock(return_value="HASH001")
    frappe.response = {}
    frappe.log_error = MagicMock()
    frappe.get_traceback = MagicMock(return_value="")

    def get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
        if doctype == "qp_SP_EventLog":
            return event_logs or []
        if doctype == "qp_SP_Alert":
            return alerts or []
        if doctype == "qp_SP_TimelineEntry":
            return timeline_entries or []
        return []

    frappe.get_all = get_all
    return frappe, utils


def _event(event_code, status, attempt_date, response=None):
    import json
    return {
        "event_code": event_code,
        "status": status,
        "attempt_date": attempt_date,
        "response": json.dumps(response if response is not None else {"Result": 0}),
        "error_message": "",
    }


def _alert(alert_message, alert_type="Alerta", alert_date="2026-09-01 09:00:00"):
    return {
        "alert_date": alert_date,
        "alert_message": alert_message,
        "alert_type": alert_type,
    }


def _entry(entry_type, new_state=None, message="", entry_date="2026-09-01 08:00:00"):
    return {
        "entry_type": entry_type,
        "message": message,
        "old_state": None,
        "new_state": new_state,
        "entry_by": "Admin Name",
        "entry_date": entry_date,
    }


class TestGetNotificationsReal(unittest.TestCase):

    def _run(self, event_logs=None, alerts=None, entries=None, doc_state="PA"):
        frappe, utils = _make_frappe(event_logs, alerts, entries, doc_state)
        patcher = patch.dict(
            sys.modules,
            {"frappe": frappe, "frappe.utils": utils},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        from qp_supplier_front.resources.documenteme import timeline as tl
        with patch.object(tl.runtime, "resolve", return_value={"data": None}):
            tl.get_notifications("D1")
        return frappe.response["message"]

    def test_resumen_y_alertas(self):
        message = self._run(
            event_logs=[
                _event("030", 200, "2026-09-01 10:00:00"),
                _event("032", 200, "2026-09-01 10:01:00"),
                _event("033", 500, "2026-09-01 10:05:00",
                       response={"Message": "boom"}),
            ],
            alerts=[_alert("No se ha podido notificar", "ErrorUrgente")],
            entries=[_entry("estado", "PA")],
            doc_state="PA",
        )
        self.assertEqual(message["status"], 200)
        data = message["data"]
        summary = data["summary"]
        self.assertEqual(
            [item["status"] for item in summary], ["ok", "ok", "en_proceso"])
        timeline = data["events"]
        self.assertEqual([item["status"] for item in timeline],
                         ["en_proceso", "ok", "ok"])
        self.assertEqual(len(data["alerts"]), 1)
        self.assertEqual(data["alerts"][0]["alert_type"], "ErrorUrgente")
        self.assertEqual(len(data["state_entries"]), 1)
        self.assertEqual(data["state_entries"][0]["type"], "estado")

    def test_sin_eventos_devuelve_vacio(self):
        message = self._run(event_logs=[], alerts=[], entries=[], doc_state="E")
        self.assertEqual(message["status"], 200)
        data = message["data"]
        self.assertEqual(data["summary"], [])
        self.assertEqual(data["events"], [])
        self.assertEqual(data["alerts"], [])


class TestGetNotificationsMemory(unittest.TestCase):

    def _seed(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", {
            "name": "999999999:F1", "nvfac_esta": "PA", "nvfac_nume": "F1",
        })
        store.insert("qp_SP_EventLog", {
            "parent": "999999999:F1", "event_code": "030", "status": 200,
            "attempt_date": "2026-09-01 10:00:00",
            "response": '{"Result": 0}',
        })
        store.insert("qp_SP_EventLog", {
            "parent": "999999999:F1", "event_code": "032", "status": 200,
            "attempt_date": "2026-09-01 10:01:00",
            "response": '{"Result": 0}',
        })
        store.insert("qp_SP_EventLog", {
            "parent": "999999999:F1", "event_code": "033", "status": 500,
            "attempt_date": "2026-09-01 10:05:00",
            "response": '{"Message": "boom"}',
        })
        store.insert("qp_SP_Alert", {
            "parent": "999999999:F1", "status": "Abierta",
            "alert_message": "Alerta de prueba", "alert_type": "Alerta",
            "alert_date": "2026-09-01 09:00:00",
        })
        store.insert("qp_SP_TimelineEntry", {
            "parent": "999999999:F1", "entry_type": "estado",
            "message": "cambio", "entry_by": "Admin", "entry_date": "2026-09-01 09:00:00",
            "old_state": "E", "new_state": "PA",
        })
        return store

    def _run(self, store):
        frappe_mock = types.ModuleType("frappe")
        utils = types.ModuleType("frappe.utils")
        utils.get_fullname = lambda user: user
        frappe_mock.utils = utils

        def _whitelist(*args, **kwargs):
            def decorator(fn):
                return fn
            return decorator
        frappe_mock.whitelist = _whitelist
        frappe_mock.response = {}
        frappe_mock.db = MagicMock()
        frappe_mock.log_error = MagicMock()

        def get_all(*args, **kwargs):
            return []
        frappe_mock.get_all = get_all
        patcher = patch.dict(
            sys.modules,
            {"frappe": frappe_mock, "frappe.utils": utils},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        from qp_supplier_front.resources.documenteme import timeline as tl
        facade = DataFacade(store=store)
        with patch.object(tl.runtime, "resolve", return_value={"data": facade}):
            tl.get_notifications("999999999:F1")
        return frappe_mock.response["message"]

    def test_memoria_resumen_y_historial(self):
        store = self._seed()
        message = self._run(store)
        self.assertEqual(message["status"], 200)
        data = message["data"]
        self.assertEqual(
            [item["status"] for item in data["summary"]],
            ["ok", "ok", "en_proceso"],
        )
        self.assertEqual(len(data["alerts"]), 1)
        self.assertEqual(data["alerts"][0]["alert_message"], "Alerta de prueba")
        self.assertEqual(
            [e["type"] for e in data["state_entries"]], ["estado"])


if __name__ == "__main__":
    unittest.main()