# -*- coding: utf-8 -*-
"""
test_approve_base_simulation.py
===============================
Pruebas unitarias del cableado de simulacion en la aprobacion
(resources/documenteme/_approve_base.py):
  - seleccion del send_request_fn simulado vs real segun el flag.
  - actor automatico de confirmacion BC tras aprobar (simulation_confirmation).

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_approve_base_simulation.py -v
"""
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import _approve_base as infra  # noqa: E402
from qp_supplier_front.resources.documenteme import simulation  # noqa: E402


class TestApproveDocumentsCoreSimulation(unittest.TestCase):

    EMPTY_RESULT = {"approved": [], "errors": []}

    def _run(self, mocks, doc_names, send_request_fn=None, force=False):
        return infra.approve_documents_core(
            doc_names,
            send_request_fn=send_request_fn,
            force=force,
        )

    def _patched(self, simulation_enabled=True, approve_result=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        mocks = {
            "approve_documents": stack.enter_context(
                patch.object(infra, "approve_documents",
                             return_value=approve_result or self.EMPTY_RESULT)
            ),
            "is_simulation_enabled": stack.enter_context(
                patch.object(infra.simulation, "is_simulation_enabled",
                             return_value=simulation_enabled)
            ),
            "run_simulated_confirmation": stack.enter_context(
                patch.object(infra.simulation, "run_simulated_confirmation",
                             return_value=[])
            ),
        }
        return mocks

    def test_simulacion_activa_usa_send_simulado(self):
        mocks = self._patched(simulation_enabled=True)
        self._run(mocks, ["DOC1"])
        send_fn = mocks["approve_documents"].call_args[1]["send_request_fn"]
        self.assertIs(send_fn, simulation.send_purchase_invoice_request)

    def test_simulacion_inactiva_usa_send_real(self):
        mocks = self._patched(simulation_enabled=False)
        self._run(mocks, ["DOC1"])
        send_fn = mocks["approve_documents"].call_args[1]["send_request_fn"]
        self.assertIs(send_fn, infra.send_purchase_invoice_request)

    def test_con_send_request_fn_explicito_lo_respeta(self):
        mocks = self._patched(simulation_enabled=True)
        custom = lambda *a, **k: ({}, 200)
        self._run(mocks, ["DOC1"], send_request_fn=custom)
        send_fn = mocks["approve_documents"].call_args[1]["send_request_fn"]
        self.assertIs(send_fn, custom)

    def test_simulacion_activa_dispara_confirmacion(self):
        approved = [{"name": "D1", "nvfac_nume": "FAC-1", "doc_number": "SIMFAC-1"}]
        conf_result = [{"doc_number": "SIMFAC-1", "confirmation_id": "SIMCONF-SIMFAC-1", "ok": True}]
        mocks = self._patched(simulation_enabled=True, approve_result={"approved": approved, "errors": []})
        mocks["run_simulated_confirmation"].return_value = conf_result

        result = self._run(mocks, ["D1"])

        mocks["run_simulated_confirmation"].assert_called_once_with(approved)
        self.assertEqual(result["simulation_confirmation"], conf_result)

    def test_simulacion_activa_sin_aprobados_no_pone_campo(self):
        mocks = self._patched(simulation_enabled=True, approve_result={"approved": [], "errors": []})
        result = self._run(mocks, ["DOC1"])
        mocks["run_simulated_confirmation"].assert_called_once_with([])
        self.assertEqual(result.get("simulation_confirmation"), [])

    def test_simulacion_inactiva_no_dispara_confirmacion(self):
        mocks = self._patched(simulation_enabled=False,
                              approve_result={"approved": [{"doc_number": "X"}], "errors": []})
        result = self._run(mocks, ["DOC1"])
        mocks["run_simulated_confirmation"].assert_not_called()
        self.assertNotIn("simulation_confirmation", result)


if __name__ == "__main__":
    unittest.main()