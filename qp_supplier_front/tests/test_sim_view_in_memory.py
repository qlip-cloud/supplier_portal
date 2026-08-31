# -*- coding: utf-8 -*-
"""
test_sim_view_in_memory.py
==========================
Vista documenteme en memoria: con el facade (data) del store, pagination,
enrich (lineas/adjuntos/allowance/asignacion) y acceso por rol leen del store
y no de la DB real.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sim_view_in_memory.py -v
"""
import unittest

from qp_supplier_front.services.pagination import get_paginated_filtered
from qp_supplier_front.services.enrich_document_list import enrich_document_list
from qp_supplier_front.services.documenteme_access import (
    get_assigned_sync_line_names,
)
from qp_supplier_front.simulation.data_facade import DataFacade
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


class TestSimViewInMemory(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.store.insert("qp_SP_DocumentDetail", {
            "name": "999999999:SIM-FAC-0002",
            "nvfac_nume": "SIM-FAC-0002",
            "nvpro_ndoc": SIM_NIT,
            "nvfac_esta": "A",
            "nvfac_fech": "2026-08-25T10:00:00",
            "nvfac_orde": "",
            "document_sync_line": "999999999:SIM-FAC-0002",
        })
        self.store.insert("qp_SP_DetailLine", {
            "parent": "999999999:SIM-FAC-0002",
            "parenttype": "qp_SP_DocumentDetail",
            "nvpro_codi": "ITEM-2", "nvdet_tcan": 2, "nvdet_valo": 400000,
            "nvdet_stot": 800000,
        })
        self.store.insert("qp_SP_DocumentAttach", {
            "parent": "999999999:SIM-FAC-0002",
            "parenttype": "qp_SP_DocumentDetail",
            "file_name": "doc.pdf", "file_type": "PDF", "file_url": "/doc.pdf",
        })
        self.store.insert("qp_SP_DocumentSyncLine", {
            "name": "999999999:SIM-FAC-0002", "assigned_to": "user@x.com",
        })
        self.data = DataFacade(store=self.store)

    def test_paginacion_lee_del_store(self):
        docs = get_paginated_filtered(
            0, "qp_SP_DocumentDetail", "nvfac_fech", {}, data=self.data)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["name"], "999999999:SIM-FAC-0002")

    def test_enrich_agrega_lineas_adjuntos_asignacion_y_detalle(self):
        self.store.insert("qp_SP_PurchaseInvoiceBC", {
            "invoice_id": "SIMF2",
            "purchase_invoice": "999999999:SIM-FAC-0002",
            "confirmation_id": "CONF-1",
        })
        self.store.insert("qp_SP_Alert", {
            "parent": "999999999:SIM-FAC-0002",
            "parenttype": "qp_SP_DocumentDetail",
            "status": "Abierta",
            "alert_message": "Falta OC",
        })
        doc = get_paginated_filtered(
            0, "qp_SP_DocumentDetail", "nvfac_fech", {}, data=self.data)[0]
        enrich_document_list([doc], "qp_SP_DocumentDetail", data=self.data)

        self.assertEqual(len(doc["detail_lines"]), 1)
        self.assertEqual(doc["detail_lines"][0]["nvpro_codi"], "ITEM-2")
        self.assertEqual(len(doc["attached_files"]), 1)
        self.assertEqual(doc["non_xml_count"], 1)
        self.assertEqual(doc["assigned_to_ids"], ["user@x.com"])
        self.assertEqual(doc["factura_interna"], "CONF-1")
        self.assertTrue(doc["has_alert"])

    def test_access_devuelve_sync_lines_asignadas(self):
        names = get_assigned_sync_line_names("user@x.com", data=self.data)
        self.assertEqual(names, ["999999999:SIM-FAC-0002"])


if __name__ == "__main__":
    unittest.main()