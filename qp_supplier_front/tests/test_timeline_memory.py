# -*- coding: utf-8 -*-
"""
test_timeline_memory.py
========================
Pruebas del timeline de facturas documenteme en modo simulador:
nucleo puro (uses_cases/documenteme/timeline.py) y adaptador in-memory
(simulation/timeline_memory.py), incluida la integracion con los puntos de
transicion de estado en memoria (memory_create_document_detail,
memory_mark_registered, reject_memory.run_reject).

Solo memoria: frappe se mockea para algunos puntos, sin base real.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_timeline_memory.py -v
"""
import unittest
from unittest.mock import patch

from qp_supplier_front.simulation import documents_memory, reject_memory, seeds
from qp_supplier_front.simulation.store import MemoryStore
from qp_supplier_front.simulation.timeline_memory import MemoryTimelineAdapter
from qp_supplier_front.uses_cases.documenteme.timeline import (
    build_comment_entry,
    build_creation_entry,
    build_state_entry,
    order_desc,
)

SIM_NIT = "999999999"


class TestPureCore(unittest.TestCase):

    def test_build_creation_entry(self):
        entry = build_creation_entry("E", "Admin", "2026-09-01 10:00:00")
        self.assertEqual(entry["type"], "creacion")
        self.assertEqual(entry["message"], "Factura registrada en el sistema")
        self.assertEqual(entry["new_state"], "E")
        self.assertIsNone(entry["old_state"])
        self.assertEqual(entry["entry_by"], "Admin")

    def test_build_state_entry(self):
        entry = build_state_entry("E", "V", "Admin", "2026-09-01 11:00:00")
        self.assertEqual(entry["type"], "estado")
        self.assertEqual(entry["message"],
                         "Cambio de estado: Registrado -> Lista para Registro")
        self.assertEqual(entry["old_state"], "E")
        self.assertEqual(entry["new_state"], "V")

    def test_build_state_entry_label_estado_rechazo(self):
        entry = build_state_entry("E", "PR", "Admin", "2026-09-01 11:00:00")
        self.assertEqual(entry["message"],
                         "Cambio de estado: Registrado -> En proceso de rechazo")

    def test_build_comment_entry(self):
        entry = build_comment_entry("Revisar monto", "Admin", "2026-09-01 12:00:00")
        self.assertEqual(entry["type"], "comentario")
        self.assertEqual(entry["message"], "Revisar monto")

    def test_order_desc(self):
        entries = [
            build_comment_entry("a", "u", "2026-09-01 09:00:00"),
            build_state_entry("E", "V", "u", "2026-09-01 11:00:00"),
            build_creation_entry("E", "u", "2026-09-01 08:00:00"),
        ]
        ordered = order_desc(entries)
        self.assertEqual(
            [e["type"] for e in ordered],
            ["estado", "comentario", "creacion"],
        )


def _seed_doc(store, name="D1", estado="E"):
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": name, "nvpro_ndoc": SIM_NIT,
        "nvfac_esta": estado,
    })


class TestMemoryTimelineAdapter(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.adapter = MemoryTimelineAdapter(self.store)

    def test_add_comment_y_get(self):
        _seed_doc(self.store)
        entry = self.adapter.add_comment("D1", "Revisar monto")
        self.assertEqual(entry["type"], "comentario")
        rows = self.store.query("qp_SP_TimelineEntry",
                                filters={"parent": "D1"})
        self.assertEqual(len(rows), 1)
        entries = self.adapter.get("D1")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["message"], "Revisar monto")

    def test_set_state_cambia_estado_y_loguea(self):
        _seed_doc(self.store, estado="E")
        entry = self.adapter.set_state("D1", "V")
        self.assertEqual(entry["type"], "estado")
        self.assertEqual(entry["old_state"], "E")
        self.assertEqual(entry["new_state"], "V")
        self.assertEqual(
            self.store.get_value("qp_SP_DocumentDetail", "D1", "nvfac_esta"),
            "V",
        )

    def test_set_state_mismo_estado_no_op(self):
        _seed_doc(self.store, estado="V")
        self.assertIsNone(self.adapter.set_state("D1", "V"))
        self.assertEqual(
            len(self.store.query("qp_SP_TimelineEntry",
                                 filters={"parent": "D1"})), 0)

    def test_set_state_extra_fields(self):
        _seed_doc(self.store, estado="BCC")
        self.adapter.set_state("D1", "A", extra_fields={"qp_is_event_completed": 1})
        row = self.store.get("qp_SP_DocumentDetail", "D1")
        self.assertEqual(row["nvfac_esta"], "A")
        self.assertEqual(row["qp_is_event_completed"], 1)

    def test_set_state_con_old_state_explicito(self):
        _seed_doc(self.store, estado="BCC")
        entry = self.adapter.set_state("D1", "A", old_state="E")
        self.assertEqual(entry["old_state"], "E")

    def test_record_creation(self):
        _seed_doc(self.store, estado="E")
        entry = self.adapter.record_creation("D1")
        self.assertEqual(entry["type"], "creacion")
        self.assertEqual(entry["new_state"], "E")

    def test_get_excluye_event_logs_de_documenteme(self):
        _seed_doc(self.store)
        self.adapter.add_comment("D1", "c1", now="2026-09-01 09:00:00")
        self.store.insert("qp_SP_EventLog", {
            "parent": "D1", "event_code": "033", "attempt_date": "2026-09-01 10:00:00",
        })
        entries = self.adapter.get("D1")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "comentario")

    def test_get_ordena_desc_por_fecha(self):
        _seed_doc(self.store)
        self.adapter.add_comment("D1", "viejo", now="2026-09-01 08:00:00")
        self.adapter.add_comment("D1", "nuevo", now="2026-09-01 12:00:00")
        entries = self.adapter.get("D1")
        self.assertEqual([e["message"] for e in entries], ["nuevo", "viejo"])


class TestMemoryIntegration(unittest.TestCase):

    def test_create_document_detail_registra_creacion(self):
        store = MemoryStore()
        documents_memory.memory_create_document_detail(
            store, "SYNC1", {"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT,
                             "Nvfac_esta": "E"}, []
        )
        adapter = MemoryTimelineAdapter(store)
        entries = adapter.get("{}:F1".format(SIM_NIT))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "creacion")
        self.assertEqual(entries[0]["new_state"], "E")

    def test_create_document_detail_resync_loguea_cambio_estado(self):
        store = MemoryStore()
        name = "{}:F1".format(SIM_NIT)
        documents_memory.memory_create_document_detail(
            store, "SYNC1", {"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT,
                             "Nvfac_esta": "E"}, []
        )
        documents_memory.memory_create_document_detail(
            store, "SYNC1", {"Nvfac_nume": "F1", "Nvpro_ndoc": SIM_NIT,
                             "Nvfac_esta": "V"}, []
        )
        adapter = MemoryTimelineAdapter(store)
        entries = adapter.get(name)
        types = [e["type"] for e in entries]
        self.assertEqual(sorted(types), ["creacion", "estado"])
        estado = [e for e in entries if e["type"] == "estado"][0]
        self.assertEqual(estado["old_state"], "E")
        self.assertEqual(estado["new_state"], "V")

    def test_memory_mark_registered_loguea_bcc(self):
        store = MemoryStore()
        _seed_doc(store)
        documents_memory.memory_mark_registered(store, {"name": "D1"})
        self.assertEqual(
            store.get_value("qp_SP_DocumentDetail", "D1", "nvfac_esta"),
            "BCC",
        )
        entries = MemoryTimelineAdapter(store).get("D1")
        self.assertEqual(entries[0]["type"], "estado")
        self.assertEqual(entries[0]["new_state"], "BCC")

    def test_reject_run_reject_loguea_pr_y_r(self):
        store = MemoryStore()
        seeds.seed_reject_rule(store, "RULE-NO-PO", "no_po")
        seeds.seed_master_setup(store, auto_approve=1, auto_reject="RULE-NO-PO")
        store.insert("qp_SP_DocumentDetail", {
            "name": "{}:F1".format(SIM_NIT), "nvfac_nume": "F1",
            "nvpro_ndoc": SIM_NIT, "nvfac_cont": "12345", "nvfac_esta": "E",
            "nvfac_ueve": "", "nvfac_conv": "2", "nvfac_orde": "PO-X",
        })
        with patch(
            "qp_supplier_front.resources.documenteme.runtime.is_simulation_enabled",
            return_value=True):
            result = reject_memory.run_reject(
                store, doc_names=["{}:F1".format(SIM_NIT)])
        self.assertEqual(result["rejected"], ["F1"])
        entries = MemoryTimelineAdapter(store).get("{}:F1".format(SIM_NIT))
        state_entries = [e for e in entries if e["type"] == "estado"]
        self.assertEqual(sorted([e["new_state"] for e in state_entries]),
                         ["PR", "R"])
        self.assertTrue(all(e["type"] != "evento" for e in entries))
        self.assertTrue(
            len(store.query("qp_SP_EventLog",
                            filters={"parent": "{}:F1".format(SIM_NIT)})) == 3)

    def test_reject_evento_fallido_loguea_solo_pr(self):
        store = MemoryStore()
        seeds.seed_reject_rule(store, "RULE-NO-PO", "no_po")
        seeds.seed_master_setup(store, auto_approve=1, auto_reject="RULE-NO-PO")
        store.insert("qp_SP_DocumentDetail", {
            "name": "{}:F1".format(SIM_NIT), "nvfac_nume": "F1",
            "nvpro_ndoc": SIM_NIT, "nvfac_cont": "12345", "nvfac_esta": "E",
            "nvfac_ueve": "", "nvfac_conv": "2", "nvfac_orde": "PO-X",
        })
        from qp_supplier_front.resources.documenteme import runtime, simulation
        bundle = {
            "event_http_fn": simulation.build_http_double(fail_all=True),
            "event_endpoint_fn": simulation.get_event_endpoint,
            "company_tax_id_fn": simulation.get_company_tax_id,
        }
        with patch.object(runtime, "resolve", return_value=bundle):
            result = reject_memory.run_reject(
                store, doc_names=["{}:F1".format(SIM_NIT)])
        self.assertEqual(result["pending"], ["F1"])
        entries = MemoryTimelineAdapter(store).get("{}:F1".format(SIM_NIT))
        state_entries = [e for e in entries if e["type"] == "estado"]
        self.assertEqual([e["new_state"] for e in state_entries], ["PR"])


if __name__ == "__main__":
    unittest.main()