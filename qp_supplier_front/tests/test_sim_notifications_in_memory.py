# -*- coding: utf-8 -*-
"""
test_sim_notifications_in_memory.py
====================================
Simulacion en memoria de las notificaciones y alertas:

- get_notifications (modal del icono de alerta) con datos sembrados por los
  flujos simulados (rechazo/aprobacion) y con el facade del store.
- Limpieza del log: re-envio OK de 030/032 actualiza su fila (no duplica) y
  el 033 fallido conserva el historial; en memoria se replica via el upsert.
- Severidad del icono (alert_severity) y conversacion (get_conversation /
  mark_conversation_read) en el modal de comentarios.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_notifications_in_memory -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
from qp_supplier_front.resources.documenteme import runtime as doc_runtime
from qp_supplier_front.services.enrich_document_detail import enrich_document_detail
from qp_supplier_front.simulation import documents_memory, seeds
from qp_supplier_front.simulation import reject_memory
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"

# Dict response compartido por todos los mocks de frappe: el modulo
# response.py vincula su global "frappe" al primer mock que ve; al compartir el
# dict, cualquier lectura desde un mock posterior sigue viendo el mensaje.
_SHARED_RESPONSE = {}


def _make_frappe_module():
    m = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")
    utils.get_fullname = lambda user: user
    m.utils = utils

    def _whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    m.whitelist = _whitelist
    m.response = _SHARED_RESPONSE
    m.db = MagicMock()
    m.log_error = MagicMock()

    def get_all(*args, **kwargs):
        return []
    m.get_all = get_all
    return m, utils


def _call(facade, fn_name, doc_name):
    """Invoca un endpoint de resources/documenteme/timeline en modo memoria."""
    m, utils = _make_frappe_module()
    patcher = patch.dict(sys.modules, {"frappe": m, "frappe.utils": utils})
    patcher.start()
    try:
        from qp_supplier_front.resources.documenteme import timeline as tl
        _SHARED_RESPONSE.clear()
        fn = getattr(tl, fn_name)
        with patch.object(tl.runtime, "resolve", return_value={"data": facade}):
            fn(doc_name)
        return dict(_SHARED_RESPONSE)["message"]
    finally:
        patcher.stop()


def _doc(store, name, nume, estado="E", conv="2", orde=None, ueve=""):
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": nume, "nvpro_ndoc": SIM_NIT,
        "nvfac_cont": "12345", "nvfac_esta": estado, "nvfac_ueve": ueve,
        "nvfac_conv": conv, "nvfac_orde": orde or "",
    })


def _http_ok(payload, url, headers, method):
    return {"Result": 0, "Description": "OK"}, 200


class TestSimNotificationsReject(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        seeds.seed_reject_rule(self.store, "RULE-NO-PO", "no_po")
        seeds.seed_master_setup(self.store, auto_approve=1, auto_reject="RULE-NO-PO")

    def test_rechazo_exitoso_resumen_ok(self):
        _doc(self.store, "{}:F1".format(SIM_NIT), "F1", conv="2", orde="PO-X")
        with patch(
            "qp_supplier_front.resources.documenteme.runtime.is_simulation_enabled",
            return_value=True):
            result = reject_memory.run_reject(
                self.store, doc_names=["{}:F1".format(SIM_NIT)])
        self.assertEqual(result["rejected"], ["F1"])

        facade = DataFacade(store=self.store)
        message = _call(facade, "get_notifications", "{}:F1".format(SIM_NIT))
        self.assertEqual(message["status"], 200)
        data = message["data"]
        self.assertEqual(
            [(s["event_code"], s["status"]) for s in data["summary"]],
            [("030", "ok"), ("032", "ok"), ("031", "ok")],
        )
        self.assertEqual(data["alerts"], [])
        # Entradas de creacion/cambio de estado en el modal de alerta
        self.assertEqual(
            sorted(e["type"] for e in data["state_entries"]), ["estado", "estado"])
        estados = [
            (e["old_state"], e["new_state"])
            for e in data["state_entries"] if e["type"] == "estado"
        ]
        self.assertIn(("E", "PR"), estados)
        self.assertIn(("PR", "R"), estados)

    def test_rechazo_fallido_alerta_urgente_y_en_proceso(self):
        _doc(self.store, "{}:F1".format(SIM_NIT), "F1", conv="2", orde="PO-X")
        bundle = {
            "event_http_fn": _http_fail_all,
            "event_endpoint_fn": lambda: ("http://x", {}, "POST"),
            "company_tax_id_fn": lambda: SIM_NIT,
        }
        with patch.object(doc_runtime, "resolve", return_value=bundle):
            result = reject_memory.run_reject(
                self.store, doc_names=["{}:F1".format(SIM_NIT)])
        self.assertEqual(result["pending"], ["F1"])

        facade = DataFacade(store=self.store)
        message = _call(facade, "get_notifications", "{}:F1".format(SIM_NIT))
        data = message["data"]
        self.assertEqual(data["summary"][0]["status"], "en_proceso")
        self.assertEqual(data["summary"][0]["event_code"], "030")
        self.assertEqual(len(data["alerts"]), 1)
        self.assertEqual(data["alerts"][0]["alert_type"], "ErrorUrgente")

    def test_enrich_severidad_rechazo_fallido(self):
        _doc(self.store, "{}:F1".format(SIM_NIT), "F1", conv="2", orde="PO-X")
        bundle = {
            "event_http_fn": _http_fail_all,
            "event_endpoint_fn": lambda: ("http://x", {}, "POST"),
            "company_tax_id_fn": lambda: SIM_NIT,
        }
        with patch.object(doc_runtime, "resolve", return_value=bundle):
            reject_memory.run_reject(
                self.store, doc_names=["{}:F1".format(SIM_NIT)])

        doc = self.store.get("qp_SP_DocumentDetail", "{}:F1".format(SIM_NIT))
        facade = DataFacade(store=self.store)
        enrich_document_detail(doc, data=facade)
        self.assertEqual(doc["alert_severity"], "urgente")
        self.assertIn("030 En proceso", doc["notification_tooltip"])
        self.assertTrue(doc["notification_summary"])


class TestSimNotificationsApprovalUpsert(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()

    def test_reenvio_030_032_no_duplica_y_033_recupera(self):
        _doc(self.store, "{}:F1".format(SIM_NIT), "F1", estado="PA", conv="2")

        # Ronda 1: 030/032 OK, 033 falla -> doc PA + alerta urgente.
        def http_fail_033(payload, url, headers, method):
            if payload.get("Nveve_dian") == "033":
                return {"Result": 1, "Description": "boom"}, 200
            return {"Result": 0}, 200

        bundle = {
            "event_http_fn": http_fail_033,
            "event_endpoint_fn": lambda: ("http://x", {}, "POST"),
            "company_tax_id_fn": lambda: SIM_NIT,
        }
        with patch.object(doc_runtime, "resolve", return_value=bundle):
            ok = documents_memory.memory_run_credit_confirmation(
                self.store, "{}:F1".format(SIM_NIT))
        self.assertFalse(ok)

        events = self.store.query("qp_SP_EventLog",
                                  filters={"parent": "{}:F1".format(SIM_NIT)})
        # El fallo del 033 se codifica como Result == 1 (status HTTP 200).
        self.assertEqual([e["event_code"] for e in events], ["030", "032", "033"])
        self.assertEqual(
            set(e["event_code"] for e in events), {"030", "032", "033"})
        self.assertTrue(
            any(e["event_code"] == "033" and '"Result": 1' in e["response"]
                for e in events))
        alerts = self.store.query("qp_SP_Alert",
                                  filters={"parent": "{}:F1".format(SIM_NIT)})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "ErrorUrgente")

        # Ronda 2 (reintento desde 030): 030/032 OK otra vez -> se actualizan
        # (sigue habiendo UNA fila por codigo) y 033 OK -> se anexa.
        bundle_ok = {
            "event_http_fn": _http_ok,
            "event_endpoint_fn": lambda: ("http://x", {}, "POST"),
            "company_tax_id_fn": lambda: SIM_NIT,
        }
        with patch.object(doc_runtime, "resolve", return_value=bundle_ok):
            ok = documents_memory.memory_run_credit_confirmation(
                self.store, "{}:F1".format(SIM_NIT))
        self.assertTrue(ok)

        events = self.store.query("qp_SP_EventLog",
                                  filters={"parent": "{}:F1".format(SIM_NIT)})
        by_code = {}
        for e in events:
            by_code.setdefault(e["event_code"], []).append(e)
        self.assertEqual(len(by_code["030"]), 1, "030 no debe duplicarse")
        self.assertEqual(len(by_code["032"]), 1, "032 no debe duplicarse")
        self.assertEqual(len(by_code["033"]), 2)
        self.assertIn('"Result": 1', by_code["033"][0]["response"])
        self.assertIn('"Result": 0', by_code["033"][1]["response"])

        doc = self.store.get("qp_SP_DocumentDetail", "{}:F1".format(SIM_NIT))
        self.assertEqual(doc["nvfac_esta"], "A")

        facade = DataFacade(store=self.store)
        message = _call(facade, "get_notifications", "{}:F1".format(SIM_NIT))
        self.assertEqual(message["status"], 200)
        summary = message["data"]["summary"]
        self.assertEqual([s["status"] for s in summary], ["ok", "ok", "ok"])
        self.assertEqual(message["data"]["alerts"], [])


def _http_fail_all(payload, url, headers, method):
    return {"Result": 1, "Description": "Error simulado"}, 200


class TestSimConversationReadMemory(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        _doc(self.store, "{}:F1".format(SIM_NIT), "F1", estado="E")

    def test_lectura_por_usuario_en_memoria(self):
        facade = DataFacade(store=self.store)

        # Comentario ajeno (queda sin leer para "Administrator" por defecto).
        facade.timeline.add_comment(
            "{}:F1".format(SIM_NIT), "Revisar monto", user="Otro")
        message = _call(facade, "get_conversation", "{}:F1".format(SIM_NIT))
        self.assertTrue(message["data"]["has_unread"])
        self.assertEqual(message["data"]["unread_count"], 1)
        self.assertEqual(len(message["data"]["comments"]), 1)

        # Marcar leido -> sin no-leidos.
        message = _call(facade, "mark_conversation_read", "{}:F1".format(SIM_NIT))
        self.assertFalse(message["data"]["has_unread"])

        message = _call(facade, "get_conversation", "{}:F1".format(SIM_NIT))
        self.assertFalse(message["data"]["has_unread"])

    def test_comentario_propio_no_cuenta_como_no_leido(self):
        facade = DataFacade(store=self.store)
        facade.timeline.add_comment(
            "{}:F1".format(SIM_NIT), "Mio", user="Administrator")
        message = _call(facade, "get_conversation", "{}:F1".format(SIM_NIT))
        self.assertFalse(message["data"]["has_unread"])

    def test_unread_en_enrich(self):
        facade = DataFacade(store=self.store)
        facade.timeline.add_comment(
            "{}:F1".format(SIM_NIT), "Alguien", user="Otro")
        doc = self.store.get("qp_SP_DocumentDetail", "{}:F1".format(SIM_NIT))
        enrich_document_detail(doc, data=facade)
        self.assertTrue(doc["has_unread_conversation"])


if __name__ == "__main__":
    unittest.main()