# -*- coding: utf-8 -*-
"""
test_auto_approve.py
====================
Pruebas unitarias para resources/documenteme/auto_approve.py.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_approve.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.resources.documenteme import auto_approve as infra  # noqa: E402
from qp_supplier_front.resources.documenteme import _approve_base as base  # noqa: E402


def _doc(name="DOC1", nvfac_esta="E", nvfac_orde="45238", nvfac_rece="R108349",
         nvfac_totp=50000, nvfac_ueve=None, nvfac_conv=None):
    return {
        "name": name,
        "nvfac_nume": name,
        "nvfac_orde": nvfac_orde,
        "nvfac_rece": nvfac_rece,
        "nvfac_totp": nvfac_totp,
        "nvfac_stot": 50000,
        "nvfac_esta": nvfac_esta,
        "nvfac_ueve": nvfac_ueve,
        "nvfac_conv": nvfac_conv,
    }


class TestIsAutoApproveEnabled(unittest.TestCase):

    def test_habilitado(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = 1
        with patch.object(infra, "frappe", frappe_mock):
            self.assertTrue(infra.is_auto_approve_enabled())
        frappe_mock.db.get_single_value.assert_called_once_with(
            "qp_SP_MasterSetup", "auto_approve"
        )

    def test_deshabilitado(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = 0
        with patch.object(infra, "frappe", frappe_mock):
            self.assertFalse(infra.is_auto_approve_enabled())


class TestGetAnalysisCandidates(unittest.TestCase):

    def test_filtra_estados_no_definitivos(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [_doc()]

        with patch.object(infra, "frappe", frappe_mock):
            candidates = infra.get_analysis_candidates()

        filters = frappe_mock.get_all.call_args[1]["filters"]
        self.assertEqual(filters["nvfac_ueve"], ["is", "not set"])
        self.assertEqual(filters["nvfac_esta"], ["in", ("E", "V", "T")])


class TestPromoteEligibleToV(unittest.TestCase):

    def _frappe(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [
            _doc(name="DOC1", nvfac_esta="E"),
            _doc(name="DOC2", nvfac_esta="V"),
            _doc(name="DOC3", nvfac_esta="E", nvfac_orde=None),
        ]
        return frappe_mock

    def test_promueve_elegibles_a_v(self):
        frappe_mock = self._frappe()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "po_exists", return_value=True), \
             patch.object(infra, "receipts_total", return_value=50000):
            promoted = infra.promote_eligible_to_v()

        self.assertEqual(promoted, ["DOC1"])
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "DOC1", "nvfac_esta", "V"
        )
        frappe_mock.db.commit.assert_called()

    def test_no_reescribe_ya_en_v(self):
        frappe_mock = self._frappe()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "po_exists", return_value=True), \
             patch.object(infra, "receipts_total", return_value=50000):
            infra.promote_eligible_to_v()

        set_calls = [
            call[0][1] for call in frappe_mock.db.set_value.call_args_list
        ]
        self.assertNotIn("DOC2", set_calls)

    def test_no_promueve_quien_no_cumple_regla(self):
        frappe_mock = self._frappe()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "po_exists", return_value=True), \
             patch.object(infra, "receipts_total", return_value=None):
            promoted = infra.promote_eligible_to_v()

        self.assertEqual(promoted, [])

    def test_promueve_contado_sin_oc_ni_recibos(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [
            _doc(name="DOC1", nvfac_esta="E", nvfac_orde=None,
                 nvfac_rece=None, nvfac_conv="1"),
        ]

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "po_exists", return_value=False), \
             patch.object(infra, "receipts_total", return_value=None):
            promoted = infra.promote_eligible_to_v()

        self.assertEqual(promoted, ["DOC1"])
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "DOC1", "nvfac_esta", "V"
        )

    def test_get_analysis_candidates_incluye_nvfac_conv(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [_doc()]

        with patch.object(infra, "frappe", frappe_mock):
            infra.get_analysis_candidates()

        fields = frappe_mock.get_all.call_args[1]["fields"]
        self.assertIn("nvfac_conv", fields)


class TestGetVDocNames(unittest.TestCase):

    def test_filtra_solo_estado_v(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = ["DOC1"]

        with patch.object(infra, "frappe", frappe_mock):
            names = infra.get_v_doc_names()

        filters = frappe_mock.get_all.call_args[1]["filters"]
        self.assertEqual(filters["nvfac_esta"], "V")
        self.assertEqual(filters["nvfac_ueve"], ["is", "not set"])


class TestRunAutoApprove(unittest.TestCase):

    def test_deshabilitado_no_hace_nada(self):
        with patch.object(infra, "frappe", MagicMock()), \
             patch.object(infra, "is_auto_approve_enabled", return_value=False), \
             patch.object(infra, "promote_eligible_to_v") as promote, \
             patch.object(infra, "get_v_doc_names") as get_v:
            result = infra.run_auto_approve()

        self.assertTrue(result["skipped"])
        promote.assert_not_called()
        get_v.assert_not_called()

    def test_sin_docs_v_no_encola(self):
        frappe_mock = MagicMock()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "is_auto_approve_enabled", return_value=True), \
             patch.object(infra, "promote_eligible_to_v", return_value=[]), \
             patch.object(infra, "get_v_doc_names", return_value=[]):
            result = infra.run_auto_approve()

        self.assertFalse(result["skipped"])
        frappe_mock.enqueue.assert_not_called()

    def test_con_docs_v_encola_job(self):
        frappe_mock = MagicMock()

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "is_auto_approve_enabled", return_value=True), \
             patch.object(infra, "promote_eligible_to_v", return_value=["DOC1"]), \
             patch.object(infra, "get_v_doc_names", return_value=["DOC1", "DOC2"]):
            result = infra.run_auto_approve()

        self.assertEqual(result["enqueued"], 2)
        frappe_mock.enqueue.assert_called_once_with(
            infra.AUTO_APPROVE_JOB_METHOD,
            doc_names=["DOC1", "DOC2"],
            queue="long",
            timeout=14400,
            job_name="auto approve documents",
        )


class TestApproveBatchJob(unittest.TestCase):

    def test_aprueba_y_loguea_errores(self):
        frappe_mock = MagicMock()

        def core(doc_names):
            return {
                "approved": [{"nvfac_nume": "FAC001"}],
                "errors": [{"nvfac_nume": "FAC002", "error": "sin recepcion"}],
            }

        with patch.object(infra, "frappe", frappe_mock), \
             patch.object(infra, "approve_documents_core", side_effect=core):
            result = infra.approve_batch_job(["DOC1", "DOC2"])

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(result["errors"]), 1)
        frappe_mock.db.commit.assert_called()
        frappe_mock.log_error.assert_called_once()
        self.assertEqual(
            frappe_mock.log_error.call_args[1]["title"],
            "Auto approve - error",
        )


class TestApproveDocumentsCoreWiring(unittest.TestCase):
    """Verifica que approve_documents_core cablea los callbacks sin NameError.

    Regresion: `mark_error_fn` se referenciaba a si mismo en lugar del callable
    real, y toda aprobacion (auto y manual) explotaba en runtime.
    """

    def test_cablea_mark_error_y_resolve_rule(self):
        frappe_mock = MagicMock()
        captured = {}

        def fake_approve_documents(*args, **kwargs):
            captured.update(kwargs)
            return {"approved": [], "errors": []}

        with patch.object(base, "frappe", frappe_mock), \
             patch.object(base, "approve_documents", side_effect=fake_approve_documents):
            result = base.approve_documents_core(
                ["DOC1"], send_request_fn=lambda *a, **k: ({"Result": 1}, 200)
            )

        self.assertEqual(result, {"approved": [], "errors": []})
        self.assertIn("mark_error_fn", captured)
        self.assertIs(captured["mark_error_fn"], base.mark_error)
        self.assertIn("resolve_rule_fn", captured)
        self.assertIs(captured["resolve_rule_fn"], base._resolve_rule)


if __name__ == "__main__":
    unittest.main()
