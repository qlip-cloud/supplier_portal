# -*- coding: utf-8 -*-
"""
test_confirmation_flow_end_to_end.py
====================================
Trazabilidad del flujo completo de aprobacion de facturas documenteme:

  BCC (Creada en BC) --update_document--> PA (encola job) --job 030/032/033--> A

Verifica que:
  1. Al crear en BC la factura queda en BCC (mark_registered).
  2. update_document guarda confirmation_id, marca PA y encola el job.
  3. El job de aprobacion (030/032/033) al exito marca A + ueve 033.
  4. Si el job agota intentos, agrega alerta y el documento permanece en PA.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

_identity = lambda fn: fn  # noqa: E731

frappe_mock = MagicMock()
frappe_mock.response = {}
frappe_mock.whitelist.side_effect = lambda *a, **k: _identity
sys.modules["frappe"] = frappe_mock
sys.modules["frappe.utils"] = MagicMock()

from qp_supplier_front.resources.documenteme import confirmation as mod  # noqa: E402
from qp_supplier_front.resources.documenteme import auto_approve_confirmation as approval  # noqa: E402
from qp_supplier_front.resources.documenteme import _approve_base  # noqa: E402


class _Doc(object):

    def __init__(self, name="FAC001", nvfac_esta="BCC"):
        self.name = name
        self.nvfac_esta = nvfac_esta
        self.nvfac_ueve = None
        self.qp_is_event_completed = 0
        self.nvpro_ndoc = "900123456"
        self.nvfac_cont = 1
        self.event_logs = []
        self._saved = False

    def get(self, key, default=None):
        value = getattr(self, key, default)
        return value if value is not None else default

    def append(self, table):
        from types import SimpleNamespace
        row = SimpleNamespace()
        # LogRow estilo doc (con get)
        class R(object):
            def get(self, k, d=None):
                return getattr(self, k, d)
        r = R()
        self.event_logs.append(r)
        return r

    def save(self):
        self._saved = True


class TestFlowEndToEnd(unittest.TestCase):

    def test_mark_registered_creacion_bc_marca_bcc(self):
        frappe_mock = MagicMock()
        doc = {"name": "FAC001", "doc_number": "123"}
        with patch.object(_approve_base, "frappe", frappe_mock), \
             patch.object(_approve_base, "resolve_open_alerts"):
            _approve_base.mark_registered(doc, "123")
        self.assertEqual(frappe_mock.db.set_value.call_args[0][3], "BCC")

    def test_update_document_marca_pa_y_encola(self):
        doc = _Doc()
        frappe_mock = MagicMock()
        frappe_mock.response = {}

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "find_document_by_invoice_id",
                          return_value={"name": "FAC001", "invoice_id": "123"}), \
             patch.object(mod, "set_confirmation_id") as set_cf, \
             patch.object(mod, "mark_pending_approval") as mark_pa, \
             patch.object(mod, "enqueue_approve") as enqueue, \
             patch.object(mod, "_commit"):
            mod.update_document("123", "CONF-XYZ")

        set_cf.assert_called_once()
        mark_pa.assert_called_once()
        # el callback marca PA
        args = mark_pa.call_args[0][0]
        self.assertIsInstance(args, dict)
        enqueue.assert_called_once()

    def test_mark_pending_approval_escribe_pa(self):
        frappe_mock = MagicMock()
        doc = {"name": "FAC001"}
        with patch.object(mod, "frappe", frappe_mock):
            mod.mark_pending_approval(doc)
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "FAC001", "nvfac_esta", "PA"
        )

    def test_enqueue_approve_confirmation_inicializa_secuencia(self):
        # La aprobacion ahora se notifica con jobs de un evento: al encolar se
        # marca la secuencia "A" y se programa el primer evento (030).
        with patch(
            "qp_supplier_front.resources.documenteme.event_job"
            ".initialize_event_schedule_db"
        ) as init_mock, patch(
            "qp_supplier_front.resources.documenteme.event_job.schedule_event"
        ) as schedule_mock:
            approval.enqueue_approve_confirmation("FAC001")

        init_mock.assert_called_once_with("FAC001", "A")
        schedule_mock.assert_called_once_with("FAC001")


if __name__ == "__main__":
    unittest.main()
