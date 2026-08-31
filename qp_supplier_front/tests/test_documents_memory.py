# -*- coding: utf-8 -*-
"""
test_documents_memory.py
========================
Pruebas del adaptador in-memory de datos del flujo documenteme
(simulation/documents_memory.py): persistencia del sync fases 1-2 y
operaciones de lectura/escritura de documentos y childs, sin base real.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_documents_memory.py -v
"""
import unittest

from qp_supplier_front.simulation.store import MemoryStore
from qp_supplier_front.simulation import documents_memory as mem

SIM_NIT = "999999999"


class TestSyncLogAndLines(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()

    def test_create_sync_log(self):
        name = mem.memory_create_sync_log(
            self.store, "COMP-1", SIM_NIT, "documenteme_list_documents",
            "param", {"Result": 0}, 200)
        self.assertTrue(name)
        log = self.store.get("qp_SP_DocumentSyncLog", name)
        self.assertEqual(log["tax_id"], SIM_NIT)
        self.assertEqual(log["status"], "Success")

    def test_sync_log_error_tiene_error_message(self):
        name = mem.memory_create_sync_log(
            self.store, "C", SIM_NIT, "ep", "p",
            {"Result": 1, "Description": "boom"}, 500)
        self.assertEqual(self.store.get("qp_SP_DocumentSyncLog", name)["error_message"], "boom")

    def test_create_sync_lines_dedupe_y_salta_ueve(self):
        mem.memory_create_sync_lines(
            self.store, "LOG-1",
            [{"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT, "Nvfac_ueve": ""},
             {"Nvfac_nume": "F2", "Nvpro_ndoc": SIM_NIT, "Nvfac_ueve": "031"}])
        self.assertTrue(self.store.exists("qp_SP_DocumentSyncLine", "999999999:F1"))
        self.assertFalse(self.store.exists("qp_SP_DocumentSyncLine", "999999999:F2"))

    def test_get_uncompleted_lines_solo_sin_completar(self):
        mem.memory_create_sync_lines(
            self.store, "LOG-1",
            [{"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT, "Nvfac_ueve": ""},
             {"Nvfac_nume": "F2", "Nvpro_ndoc": SIM_NIT, "Nvfac_ueve": ""}])
        mem.memory_mark_line_completed(self.store, "999999999:F1")
        lines = mem.memory_get_uncompleted_lines(self.store)
        self.assertEqual([l["name"] for l in lines], ["999999999:F2"])

    def test_get_log_company_tax_id(self):
        name = mem.memory_create_sync_log(self.store, "C", SIM_NIT, "ep", "p", {}, 200)
        self.assertEqual(
            mem.memory_get_log_company_tax_id(self.store, name), SIM_NIT)

    def test_log_sync_attempt(self):
        row = {"parent": "999999999:F1"}
        mem.memory_log_sync_attempt(self.store, "999999999:F1", "Success", None, {})
        attempts = self.store.query("qp_SP_DetailSyncAttempt",
                                    filters={"parent": "999999999:F1"})
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["status"], "Success")

    def test_mark_line_completed(self):
        mem.memory_create_sync_lines(
            self.store, "LOG-1",
            [{"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT, "Nvfac_ueve": ""}])
        mem.memory_mark_line_completed(self.store, "999999999:F1")
        self.assertEqual(
            self.store.get("qp_SP_DocumentSyncLine", "999999999:F1")["is_completed"], 1)


class _DetailFixture(object):

    @staticmethod
    def data():
        return {
            "Nvfac_nume": "SIM-FAC-0001",
            "Nvpro_ndoc": SIM_NIT,
            "Nvfac_esta": "E",
            "Nvfac_conv": "2",
            "Nvfac_fech": "2026-08-25T10:00:00",
            "Detalle": [{
                "Nvdet_cont": "1", "Nvpro_codi": "ITEM-1",
                "Nvdet_desc": "ITEM", "Nvdet_tcan": 2, "Nvdet_valo": 500,
                "Nvdet_stot": 1000, "lImpuestos": [],
            }],
        }


class TestCreateDocumentDetail(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()

    def test_crea_detalle_con_childs(self):
        doc = mem.memory_create_document_detail(
            self.store, "999999999:SIM-FAC-0001",
            _DetailFixture.data(), [])
        self.assertEqual(doc.name, "999999999:SIM-FAC-0001")
        stored = self.store.get("qp_SP_DocumentDetail", doc.name)
        self.assertEqual(stored["nvfac_esta"], "E")
        lines = self.store.query("qp_SP_DetailLine",
                                 filters={"parent": doc.name})
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["nvpro_codi"], "ITEM-1")

    def test_crea_attached_files(self):
        attached = [{"Nvdoc_nomb": "f.xml", "Nvdoc_tipo": "XML", "Nvdoc_file": None}]
        doc = mem.memory_create_document_detail(
            self.store, "999999999:SIM-FAC-0001", _DetailFixture.data(), attached)
        rows = self.store.query("qp_SP_DocumentAttach", filters={"parent": doc.name})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file_name"], "f.xml")

    def test_reescritura_actualiza_sin_duplicar_childs(self):
        mem.memory_create_document_detail(
            self.store, "999999999:SIM-FAC-0001", _DetailFixture.data(), [])
        data2 = _DetailFixture.data()
        data2["Nvfac_esta"] = "V"
        mem.memory_create_document_detail(
            self.store, "999999999:SIM-FAC-0001", data2, [])
        stored = self.store.get("qp_SP_DocumentDetail", "999999999:SIM-FAC-0001")
        self.assertEqual(stored["nvfac_esta"], "V")
        self.assertEqual(
            len(self.store.query("qp_SP_DetailLine",
                                 filters={"parent": "999999999:SIM-FAC-0001"})), 1)


class TestDocumentOps(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        mem.memory_create_document_detail(
            self.store, "999999999:F1",
            {"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT, "Nvfac_esta": "E"},
            [])

    def test_query_documents(self):
        rows = mem.memory_query_documents(self.store, {"nvfac_esta": "E"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "999999999:F1")

    def test_get_document(self):
        doc = mem.memory_get_document(self.store, "999999999:F1")
        self.assertEqual(doc["nvfac_nume"], "F1")

    def test_get_document_by_number(self):
        name = mem.memory_get_document_by_number(self.store, "F1", SIM_NIT)
        self.assertEqual(name, "999999999:F1")

    def test_get_document_by_number_sin_ndoc(self):
        name = mem.memory_get_document_by_number(self.store, "F1")
        self.assertEqual(name, "999999999:F1")

    def test_set_document_value(self):
        mem.memory_set_document_value(self.store, "999999999:F1", "nvfac_esta", "V")
        self.assertEqual(
            self.store.get("qp_SP_DocumentDetail", "999999999:F1")["nvfac_esta"], "V")

    def test_update_document(self):
        mem.memory_update_document(self.store, "999999999:F1", {"qp_motive": "m"})
        self.assertEqual(
            self.store.get("qp_SP_DocumentDetail", "999999999:F1")["qp_motive"], "m")

    def test_get_child_rows(self):
        data = _DetailFixture.data()
        data["Nvfac_nume"] = "F1"
        mem.memory_create_document_detail(
            self.store, "999999999:F1", data, [])
        rows = mem.memory_get_child_rows(self.store, "qp_SP_DetailLine", "999999999:F1")
        self.assertEqual(len(rows), 1)


class TestAssignedLines(unittest.TestCase):

    def test_nombres_asignados_directos_y_child(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentSyncLine", {"name": "SL1", "assigned_to": "user@x"})
        store.insert("qp_SP_SyncLineAssignedUser", {"parent": "SL2", "user": "user@x"})
        store.insert("qp_SP_SyncLineAssignedUser", {"parent": "SL3", "user": "other"})
        names = mem.memory_get_assigned_line_names(store, "user@x")
        self.assertCountEqual(names, ["SL1", "SL2"])


class TestCount(unittest.TestCase):

    def test_count_documents(self):
        store = MemoryStore()
        mem.memory_create_document_detail(
            store, "999999999:F1",
            {"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT, "Nvfac_esta": "E"}, [])
        self.assertEqual(mem.memory_count_documents(store), 1)
        self.assertEqual(
            mem.memory_count_documents(store, {"nvfac_esta": "R"}), 0)


class TestCreditConfirmation(unittest.TestCase):

    def _seed_credit(self, store):
        store.insert("qp_SP_DocumentDetail", {
            "name": "999999999:F1", "nvfac_nume": "F1",
            "nvpro_ndoc": SIM_NIT, "nvfac_cont": "12345",
            "nvfac_esta": "PA", "nvfac_ueve": "", "nvfac_conv": "2",
        })

    def test_confirmacion_credito_llega_a_aprobado(self):
        from unittest.mock import patch

        from qp_supplier_front.resources.documenteme import runtime

        store = MemoryStore()
        self._seed_credit(store)
        with patch.object(runtime, "is_simulation_enabled", return_value=True):
            ok = mem.memory_run_credit_confirmation(store, "999999999:F1")
        self.assertTrue(ok)
        doc = store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "A")
        self.assertEqual(doc["nvfac_ueve"], "033")
        self.assertEqual(doc["qp_is_event_completed"], 1)
        events = store.query("qp_SP_EventLog",
                             filters={"parent": "999999999:F1"})
        self.assertEqual([e["event_code"] for e in events],
                         ["030", "032", "033"])

    def test_evento_fallido_deja_pa_con_alerta(self):
        from unittest.mock import patch

        from qp_supplier_front.resources.documenteme import runtime
        from qp_supplier_front.resources.documenteme import simulation

        store = MemoryStore()
        self._seed_credit(store)
        bundle = {
            "company_tax_id_fn": simulation.get_company_tax_id,
            "event_endpoint_fn": simulation.get_event_endpoint,
            "event_http_fn": simulation.build_http_double(fail_all=True),
        }
        with patch.object(runtime, "resolve", return_value=bundle):
            ok = mem.memory_run_credit_confirmation(store, "999999999:F1")
        self.assertFalse(ok)
        doc = store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "PA")
        alerts = store.query("qp_SP_Alert",
                             filters={"parent": "999999999:F1"})
        self.assertEqual(len(alerts), 1)

    def test_enqueue_approve_credito_ejecuta_confirmacion(self):
        from unittest.mock import patch

        from qp_supplier_front.resources.documenteme import runtime

        store = MemoryStore()
        self._seed_credit(store)
        with patch.object(runtime, "is_simulation_enabled", return_value=True):
            mem.memory_enqueue_approve(store, {"name": "999999999:F1"})
        doc = store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "A")


if __name__ == "__main__":
    unittest.main()