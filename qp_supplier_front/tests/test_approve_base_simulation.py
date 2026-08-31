# -*- coding: utf-8 -*-
"""
test_approve_base_simulation.py
===============================
Pruebas unitarias del cableado de aprobacion (resources/documenteme/_approve_base.py):
  - delegacion de adaptadores al composition root runtime.resolve().
  - actor de confirmacion BC tras aprobar (on_batch_approved_fn).

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_approve_base_simulation.py -v
"""
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import _approve_base as infra  # noqa: E402


def _bundle(approve_send_fn=None, on_batch_approved_fn=None):
    return {
        "approve_send_fn": approve_send_fn,
        "on_batch_approved_fn": on_batch_approved_fn,
    }


class TestApproveDocumentsCoreRuntime(unittest.TestCase):

    EMPTY_RESULT = {"approved": [], "errors": []}

    def _patched(self, bundle):
        stack = ExitStack()
        self.addCleanup(stack.close)
        return {
            "approve_documents": stack.enter_context(
                patch.object(infra, "approve_documents",
                             return_value=self.EMPTY_RESULT)
            ),
            "runtime_resolve": stack.enter_context(
                patch.object(infra.runtime, "resolve", return_value=bundle)
            ),
        }

    def test_sin_send_fn_toma_runtime(self):
        simulated = lambda *a, **k: ({}, 200)
        mocks = self._patched(_bundle(approve_send_fn=simulated))
        infra.approve_documents_core(["DOC1"])
        send_fn = mocks["approve_documents"].call_args[1]["send_request_fn"]
        self.assertIs(send_fn, simulated)
        mocks["runtime_resolve"].assert_called_once()

    def test_con_send_fn_explicito_no_usa_runtime_send(self):
        custom = lambda *a, **k: ({}, 200)
        mocks = self._patched(_bundle(approve_send_fn=lambda *a, **k: ({}, 400)))
        infra.approve_documents_core(["DOC1"], send_request_fn=custom)
        send_fn = mocks["approve_documents"].call_args[1]["send_request_fn"]
        self.assertIs(send_fn, custom)

    def test_on_batch_approved_none_no_confirma(self):
        mocks = self._patched(_bundle(on_batch_approved_fn=None))
        result = infra.approve_documents_core(["DOC1"])
        self.assertNotIn("simulation_confirmation", result)

    def test_on_batch_approved_se_ejecuta_tras_aprobacion(self):
        captured = []

        def on_batch(result):
            captured.append(result)

        bundled_on_batch = on_batch
        mocks = self._patched(_bundle(on_batch_approved_fn=bundled_on_batch))
        mock_result = {"approved": [{"doc_number": "SIMFAC-1"}], "errors": []}
        mocks["approve_documents"].return_value = mock_result

        result = infra.approve_documents_core(["DOC1"])
        self.assertEqual(captured, [mock_result])
        self.assertEqual(result, mock_result)

    def test_on_batch_approved_simulado_setea_confirmation(self):
        mock_result = {
            "approved": [{"name": "D1", "nvfac_nume": "FAC-1",
                          "doc_number": "SIMFAC-1"}],
            "errors": [],
        }
        mocks = self._patched(_bundle())
        mocks["approve_documents"].return_value = mock_result

        from qp_supplier_front.resources.documenteme import runtime
        from qp_supplier_front.resources.documenteme import simulation

        bundle = _bundle(
            approve_send_fn=lambda *a, **k: ({}, 200),
            on_batch_approved_fn=runtime._apply_simulated_confirmation,
        )
        with patch.object(infra.runtime, "resolve", return_value=bundle), \
             patch.object(simulation, "run_simulated_confirmation",
                          return_value=[{"doc_number": "SIMFAC-1", "ok": True}]):
            result = infra.approve_documents_core(["DOC1"])

        self.assertIn("simulation_confirmation", result)


if __name__ == "__main__":
    unittest.main()