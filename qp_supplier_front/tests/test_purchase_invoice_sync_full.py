# -*- coding: utf-8 -*-
"""
test_purchase_invoice_sync_full.py
==================================
Regresiones del sync full de facturas de compra:

- _has_invoices: sonda de una sola llamada por proveedor (count) para no
  recorrer ~34 ventanas historicas cuando el proveedor no tiene facturas.
- _run_supplier: en full/on_demand no abre ventanas si la sonda da vacio.
- _sweep: corta por presupuesto de tiempo en vez de quedar pegado.
- handler de qp_authorization: no registra un 404 benigno cuando se pide
  ignore_statuses=(404,).

Ejecutar con: python -m pytest qp_supplier_front/tests/test_purchase_invoice_sync_full.py -v
"""
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.uses_cases.purchase_invoice import (  # noqa: E402
    sync_by_supplier as mod,
)


def _strategy():
    return {
        "endpoints": {"per_supplier": "invoice_supplier_id"},
        "request_key": "invoices",
        "build_param": lambda supplier_id, last_date=None, now=None: str(supplier_id),
    }


class TestHasInvoices(unittest.TestCase):

    def test_vacio_no_tiene_facturas(self):
        calls = []

        def fetch(endpoint, param=None):
            calls.append((endpoint, param))
            return {"invoices": []}

        with patch.object(mod, "get_strategy", return_value=_strategy()):
            self.assertFalse(mod._has_invoices("SUP-1", "GP", fetch))
        self.assertEqual(calls, [("invoice_supplier_id", "SUP-1")])

    def test_con_datos_si_tiene_facturas(self):
        def fetch(endpoint, param=None):
            return {"invoices": [{"invoiceId": "F1"}]}

        with patch.object(mod, "get_strategy", return_value=_strategy()):
            self.assertTrue(mod._has_invoices("SUP-1", "GP", fetch))

    def test_respuesta_no_dict_asume_tiene(self):
        with patch.object(mod, "get_strategy", return_value=_strategy()):
            self.assertTrue(
                mod._has_invoices("SUP-1", "GP", lambda e, param=None: None))


class TestRunSupplierProbe(unittest.TestCase):

    def test_sin_facturas_no_abre_ventanas(self):
        with patch.object(mod, "get_strategy", return_value=_strategy()), \
             patch.object(mod, "_resolve_start") as resolve, \
             patch.object(mod, "generate_date_windows") as windows:
            result = mod._run_supplier(
                "SUP-1", "GP", "full", datetime(2026, 11, 6),
                has_invoices_fn=lambda sid, flow, fetch: False,
            )
        self.assertEqual(result, {"inserted": 0, "windows": 0})
        resolve.assert_not_called()
        windows.assert_not_called()

    def test_con_facturas_abre_ventanas(self):
        with patch.object(mod, "get_strategy", return_value=_strategy()), \
             patch.object(mod, "_resolve_start", return_value=datetime(2026, 1, 1)) as resolve, \
             patch.object(mod, "generate_date_windows", return_value=[]) as windows:
            result = mod._run_supplier(
                "SUP-1", "GP", "full", datetime(2026, 11, 6),
                has_invoices_fn=lambda sid, flow, fetch: True,
            )
        self.assertEqual(result, {"inserted": 0, "windows": 0})
        resolve.assert_called_once()
        windows.assert_called_once()


class TestSweepTimeBudget(unittest.TestCase):

    def test_corta_al_agotar_presupuesto(self):
        fake_time = MagicMock()
        fake_time.time.side_effect = [0.0, 0.0, 10.0]

        with patch.object(mod, "time", fake_time), \
             patch.object(mod, "_run_supplier",
                          return_value={"inserted": 0, "windows": 0}) as run, \
             patch.object(mod, "acquire", return_value={"token": "t"}), \
             patch.object(mod, "release"), \
             patch.object(mod, "set_checkpoint"):
            result = mod._sweep(
                "GP", ["S1", "S2", "S3"], "full", time_budget_seconds=5)

        self.assertTrue(result["stopped"])
        self.assertEqual([c.args[0] for c in run.call_args_list], ["S1"])


class TestHandlerIgnoreStatuses(unittest.TestCase):

    def _response(self, status):
        response = MagicMock()
        response.status_code = status
        response.text = "{}"
        return response

    def test_404_ignorado_no_loguea(self):
        from qp_authorization.use_case.rest import request as req
        with patch.object(req.requests, "request",
                          return_value=self._response(404)), \
             patch.object(req, "log_request_failure") as log:
            _, status = req.handler(
                "http://x/invoice", {}, {}, method="GET",
                ignore_statuses=(404,))
        self.assertEqual(status, 404)
        log.assert_not_called()

    def test_404_sin_ignorar_si_loguea(self):
        from qp_authorization.use_case.rest import request as req
        with patch.object(req.requests, "request",
                          return_value=self._response(404)), \
             patch.object(req, "log_request_failure") as log:
            req.handler("http://x/invoice", {}, {}, method="GET")
        log.assert_called_once()


if __name__ == "__main__":
    unittest.main()
