# -*- coding: utf-8 -*-
"""
test_sync_all_by_company.py
===========================
Pruebas unitarias para uses_cases/documents/sync_all_whitelist.py
Verifica que la sincronizacion global diaria itera COMPANIAS y usa el
tax_id de la compania (nvemp_nnit = tax_id de Company), no el del proveedor.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sync_all_by_company.py -v
"""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import qp_supplier_front.uses_cases.documents.sync_all_whitelist as saw
import qp_supplier_front.resources.documenteme.auto_reject as arrej
import qp_supplier_front.resources.documenteme.auto_approve as arapp
from qp_supplier_front.services.document_sync import create_sync_log


class TestSyncAllByCompany(unittest.TestCase):

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.frappe_mock.get_all.return_value = ["COMP-A", "COMP-B"]

        self.sync_by_supplier_calls = []
        self.assign_calls = []
        self.reject_results = {"rejected": ["F1"]}
        self.approve_results = {"approved": [{"nvfac_nume": "F2"}]}

        def fake_sync_by_supplier(**kwargs):
            self.sync_by_supplier_calls.append(kwargs)

        def fake_assign(doc_names=None):
            self.assign_calls.append(doc_names)

        self.patches = [
            patch.object(saw, "frappe", self.frappe_mock),
            patch.object(saw, "sync_by_supplier", side_effect=fake_sync_by_supplier),
            patch.object(saw, "sync_detail", return_value=["DOC-NEW-1", "DOC-NEW-2"]),
            patch.object(saw, "send_request_status", return_value=({}, 200)),
            patch.object(saw, "run_documenteme_auto_assign", side_effect=fake_assign),
            patch.object(saw, "_launch_reject", return_value=self.reject_results),
            patch.object(saw, "run_documenteme_auto_approve", return_value=self.approve_results),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_get_company_tax_id(self):
        company_mock = MagicMock()
        company_mock.tax_id = "111"
        self.frappe_mock.get_doc.return_value = company_mock
        self.assertEqual(saw.get_company_tax_id("COMP-A"), "111")
        self.frappe_mock.get_doc.assert_called_with("Company", "COMP-A")

    def test_sync_all_itera_companies(self):
        result = saw.sync_all()
        self.assertTrue(result["success"])
        self.assertEqual(result["companies_count"], 2)
        company_names = [call["supplier_id"] for call in self.sync_by_supplier_calls]
        self.assertEqual(company_names, ["COMP-A", "COMP-B"])

    def test_sync_all_usa_tax_id_de_company(self):
        tax_ids = {"COMP-A": "111", "COMP-B": "222"}
        self.frappe_mock.get_doc.side_effect = (
            lambda doctype, name: MagicMock(tax_id=tax_ids[name])
        )
        saw.sync_all()
        for call in self.sync_by_supplier_calls:
            name = call["supplier_id"]
            self.assertEqual(call["get_tax_id_fn"](name), tax_ids[name])

    def test_sync_all_defaults_rango_ayer(self):
        with patch.object(saw, "get_default_nvfac_fini", return_value="31/07/2026"), \
             patch.object(saw, "get_default_nvfac_ffin", return_value="31/07/2026"):
            saw.sync_all()
        for call in self.sync_by_supplier_calls:
            self.assertEqual(call["nvfac_fini"], "31/07/2026")
            self.assertEqual(call["nvfac_ffin"], "31/07/2026")

    def test_sync_all_pasa_rango_explicito(self):
        saw.sync_all(nvfac_fini="31/07/2026", nvfac_ffin="01/08/2026")
        self.assertTrue(self.sync_by_supplier_calls)
        for call in self.sync_by_supplier_calls:
            self.assertEqual(call["nvfac_fini"], "31/07/2026")
            self.assertEqual(call["nvfac_ffin"], "01/08/2026")

    def test_sync_all_usa_created_names_en_los_run_auto(self):
        result = saw.sync_all()
        self.assertTrue(result["success"])
        self.assertEqual(self.assign_calls[-1], ["DOC-NEW-1", "DOC-NEW-2"])
        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["rejected"], ["F1"])
        self.assertEqual(result["approved"], [{"nvfac_nume": "F2"}])


class TestRefreshDocuments(unittest.TestCase):
    """El boton refrescar trae facturas de forma sincrona sin lock global y
    lanza el auto-rechazo en segundo plano sobre las nuevas."""

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.frappe_mock.get_all.return_value = ["COMP-A", "COMP-B"]
        self.sync_calls = []
        self.assign_calls = []
        self.reject_calls = []

        def fake_sync_by_supplier(**kwargs):
            self.sync_calls.append(kwargs)

        def fake_assign(doc_names=None):
            self.assign_calls.append(doc_names)

        def fake_reject(doc_names):
            self.reject_calls.append(doc_names)
            return {"rejected": ["F1"]}

        self.patches = [
            patch.object(saw, "frappe", self.frappe_mock),
            patch.object(saw, "sync_by_supplier", side_effect=fake_sync_by_supplier),
            patch.object(saw, "sync_detail", return_value=["DOC-NEW-1", "DOC-NEW-2"]),
            patch.object(saw, "send_request_status", return_value=({}, 200)),
            patch.object(saw, "run_documenteme_auto_assign", side_effect=fake_assign),
            patch.object(saw, "_launch_reject", side_effect=fake_reject),
            patch.object(saw, "run_documenteme_auto_approve", return_value={"approved": []}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_refresh_documents_no_usa_lock_global(self):
        with patch.object(saw, "sync_lock") as lock_mock:
            result = saw.refresh_documents()
        self.assertTrue(result["success"])
        self.assertTrue(self.sync_calls)
        lock_mock.acquire.assert_not_called()

    def test_refresh_lanza_rechazo_en_fondo_con_nuevos(self):
        saw.refresh_documents()
        self.assertEqual(self.reject_calls, [["DOC-NEW-1", "DOC-NEW-2"]])
        self.assertEqual(self.assign_calls[-1], ["DOC-NEW-1", "DOC-NEW-2"])

    def test_refresh_siempre_encola_el_rechazo(self):
        saw.refresh_documents()
        # El refresh siempre lanza el rechazo aunque exista otro job.
        self.assertEqual(len(self.reject_calls), 1)

    def test_sync_all_error_returns_internal_error(self):
        self.frappe_mock.get_all.side_effect = RuntimeError("boom")
        result = saw.sync_all()
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Internal error")
        self.frappe_mock.db.rollback.assert_called()


class TestCreateSyncLogSupplierLink(unittest.TestCase):
    """qp_SP_DocumentSyncLog.supplier es Link->Supplier: en sync por compania
    no debe asignarse un nombre de compania inexistente como Supplier."""

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.log_mock = MagicMock()
        self.frappe_mock.new_doc.return_value = self.log_mock
        self.patch = patch.dict(sys.modules, {"frappe": self.frappe_mock})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_supplier_inexistente_no_asigna_link(self):
        self.frappe_mock.db.exists.return_value = False
        create_sync_log("COMP-X", "111", "EP", "p", {"Result": 0}, 200)
        self.log_mock.insert.assert_called_once()
        self.assertEqual(self.log_mock.tax_id, "111")

    def test_supplier_existente_asigna_link(self):
        self.frappe_mock.db.exists.return_value = True
        create_sync_log("PROV-1", "111", "EP", "p", {"Result": 0}, 200)
        self.log_mock.insert.assert_called_once()
        self.assertEqual(self.log_mock.supplier, "PROV-1")


from qp_supplier_front.uses_cases.documents.sync_detail import sync_detail
from qp_supplier_front.services.document_sync import build_detail_params


class TestBuildDetailParams(unittest.TestCase):

    def test_usa_tax_id_company_y_supplier_separados(self):
        param = build_detail_params("830005677", "900162414", "E", "SETT0501121")
        self.assertIn("nvemp_nnit=830005677", param)
        self.assertIn("nvpro_docu=900162414", param)
        self.assertIn("nvfac_esta=E", param)
        self.assertIn("nvfac_nume=SETT0501121", param)


class TestSyncDetailCompanyTaxId(unittest.TestCase):

    def _base_kwargs(self, lines, captured):
        return {
            "get_uncompleted_lines_fn": lambda: lines,
            "send_request_fn": lambda **kw: captured.append(kw) or (
                {"Result": 0, "Document": {}, "lAttached": []}, 200
            ),
            "create_document_detail_fn": lambda name, data, attached: None,
            "log_sync_attempt_fn": lambda *a, **kw: None,
            "mark_line_completed_fn": lambda name: None,
            "commit_fn": lambda: None,
        }

    def test_usa_tax_id_de_company_del_log(self):
        captured = []
        line = {
            "name": "SETT0501121",
            "document_sync_log": "LOG-1",
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        sync_detail(
            **self._base_kwargs([line], captured),
            get_company_tax_id_fn=lambda log_name: "830005677",
        )
        param = captured[0]["param"]
        self.assertIn("nvemp_nnit=830005677", param)
        self.assertIn("nvpro_docu=900162414", param)

    def test_fallback_a_nvpro_ndoc_si_log_sin_tax_id(self):
        captured = []
        line = {
            "name": "SETT0501121",
            "document_sync_log": "LOG-X",
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        sync_detail(
            **self._base_kwargs([line], captured),
            get_company_tax_id_fn=lambda log_name: None,
        )
        param = captured[0]["param"]
        self.assertIn("nvemp_nnit=900162414", param)
        self.assertIn("nvpro_docu=900162414", param)

    def test_fallback_sin_callback(self):
        captured = []
        line = {
            "name": "SETT0501121",
            "document_sync_log": None,
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        sync_detail(**self._base_kwargs([line], captured))
        param = captured[0]["param"]
        self.assertIn("nvemp_nnit=900162414", param)

    def test_marca_completado_en_exito(self):
        captured = []
        marked = []
        line = {
            "name": "SETT0501121",
            "document_sync_log": "LOG-1",
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        sync_detail(
            get_uncompleted_lines_fn=lambda: [line],
            send_request_fn=lambda **kw: ({"Result": 0, "Document": {}, "lAttached": []}, 200),
            create_document_detail_fn=lambda name, data, attached: None,
            log_sync_attempt_fn=lambda *a, **kw: None,
            mark_line_completed_fn=lambda name: marked.append(name),
            commit_fn=lambda: None,
            get_company_tax_id_fn=lambda log_name: "830005677",
        )
        self.assertEqual(marked, ["SETT0501121"])

    def test_no_marca_completado_en_error(self):
        captured = []
        marked = []
        line = {
            "name": "SETT0501121",
            "document_sync_log": "LOG-1",
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        sync_detail(
            get_uncompleted_lines_fn=lambda: [line],
            send_request_fn=lambda **kw: ({"Result": 1, "Description": "error"}, 200),
            create_document_detail_fn=lambda name, data, attached: None,
            log_sync_attempt_fn=lambda *a, **kw: None,
            mark_line_completed_fn=lambda name: marked.append(name),
            commit_fn=lambda: None,
            get_company_tax_id_fn=lambda log_name: "830005677",
        )
        self.assertEqual(marked, [])

    def test_retorna_created_names(self):
        line = {
            "name": "SETT0501121",
            "document_sync_log": "LOG-1",
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        names = sync_detail(
            get_uncompleted_lines_fn=lambda: [line],
            send_request_fn=lambda **kw: ({"Result": 0, "Document": {}, "lAttached": []}, 200),
            create_document_detail_fn=lambda name, data, attached: SimpleNamespace(name=name),
            log_sync_attempt_fn=lambda *a, **kw: None,
            mark_line_completed_fn=lambda name: None,
            commit_fn=lambda: None,
            get_company_tax_id_fn=lambda log_name: "830005677",
        )
        self.assertEqual(names, ["SETT0501121"])

    def test_created_names_ignora_errores(self):
        line = {
            "name": "SETT0501121",
            "document_sync_log": "LOG-1",
            "nvpro_ndoc": "900162414",
            "nvfac_esta": "E",
            "nvfac_nume": "SETT0501121",
        }
        names = sync_detail(
            get_uncompleted_lines_fn=lambda: [line],
            send_request_fn=lambda **kw: ({"Result": 1, "Description": "error"}, 200),
            create_document_detail_fn=lambda name, data, attached: SimpleNamespace(name=name),
            log_sync_attempt_fn=lambda *a, **kw: None,
            mark_line_completed_fn=lambda name: None,
            commit_fn=lambda: None,
            get_company_tax_id_fn=lambda log_name: "830005677",
        )
        self.assertEqual(names, [])


class TestRunAutoRejectSync(unittest.TestCase):

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.patch = patch.object(arrej, "frappe", self.frappe_mock)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_enqueue_false_no_encola_y_ejecuta_batch(self):
        rejects = [{"doc": "F1", "motive": "m", "rule": "r"}]
        with patch.object(arrej, "auto_reject_core", return_value=rejects) as core, \
             patch.object(arrej, "reject_batch_job") as batch:
            result = arrej.run_auto_reject(enqueue=False, doc_names=["F1"])
        core.assert_called_once_with(
            candidates_fn=arrej.get_candidates,
            resolve_rule_fn=arrej.resolve_rule,
            po_exists_fn=arrej.po_exists,
            receipt_for_po_fn=arrej.receipt_for_po,
            doc_names=["F1"],
        )
        batch.assert_called_once_with(rejects, http_fn=None)
        self.frappe_mock.enqueue.assert_not_called()
        self.assertEqual(result["rejected"], ["F1"])

    def test_enqueue_default_encola(self):
        rejects = [{"doc": "F1", "motive": "m", "rule": "r"}]
        with patch.object(arrej, "auto_reject_core", return_value=rejects), \
             patch.object(arrej, "reject_batch_job") as batch:
            arrej.run_auto_reject()
        self.frappe_mock.enqueue.assert_called_once()
        batch.assert_not_called()


class TestRunAutoApproveSync(unittest.TestCase):

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.patch = patch.object(arapp, "frappe", self.frappe_mock)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_enqueue_false_no_encola_y_ejecuta_batch(self):
        approved = [{"nvfac_nume": "F1", "doc_number": "BC1"}]
        with patch.object(arapp, "is_auto_approve_enabled", return_value=True) as enabled, \
             patch.object(arapp, "promote_eligible_to_v", return_value=["F1"]) as promote, \
             patch.object(arapp, "get_v_doc_names", return_value=["F1"]) as getv, \
             patch.object(arapp, "approve_batch_job",
                          return_value={"approved": approved, "errors": []}) as batch:
            result = arapp.run_auto_approve(enqueue=False, doc_names=["F1"])
        self.assertTrue(enabled.called)
        promote.assert_called_once_with(["F1"])
        getv.assert_called_once_with(["F1"])
        batch.assert_called_once_with(["F1"])
        self.frappe_mock.enqueue.assert_not_called()
        self.assertEqual(result["approved"], approved)

    def test_enqueue_default_encola(self):
        with patch.object(arapp, "is_auto_approve_enabled", return_value=True), \
             patch.object(arapp, "promote_eligible_to_v", return_value=[]), \
             patch.object(arapp, "get_v_doc_names", return_value=["F1"]), \
             patch.object(arapp, "approve_batch_job") as batch:
            result = arapp.run_auto_approve()
        self.frappe_mock.enqueue.assert_called_once()
        batch.assert_not_called()
        self.assertEqual(result["enqueued"], 1)


if __name__ == "__main__":
    unittest.main()