# -*- coding: utf-8 -*-
"""
test_document_sync.py
=====================
Pruebas unitarias para services/document_sync.py:

  - create_sync_line: reutiliza una SyncLine existente del mismo proveedor
    y numero (formato legacy siempre, incluso si el autoname cambio a
    {nvpro_ndoc}:{nvfac_nume}), evitando duplicar lineas ni forzar una
    re-sincronizacion del detalle.
  - build_sync_line_name: formato del nombre de la SyncLine.
  - create_document_detail (rama update): limpia los child rows cargados en
    memoria despues de borrarlos en BD, para que save() no re-persista rows
    viejos ni valide File links ya eliminados (LinkValidationError).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_document_sync -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.services import document_sync as ds  # noqa: E402


def _doc_data(nvfac_nume="SETT0501159", nvpro_ndoc="900162414"):
    return {
        "Nvfac_nume": nvfac_nume,
        "Nvpro_ndoc": nvpro_ndoc,
        "Nvfac_esta": "E",
        "Nvfac_orde": "48740",
    }


class TestBuildSyncLineName(unittest.TestCase):

    def test_con_proveedor_usa_prefijo(self):
        self.assertEqual(
            ds.build_sync_line_name("900162414", "SETT0501159"),
            "900162414:SETT0501159",
        )

    def test_sin_proveedor_solo_nume(self):
        self.assertEqual(ds.build_sync_line_name("", "SETT0501159"), "SETT0501159")
        self.assertEqual(ds.build_sync_line_name(None, "SETT0501159"), "SETT0501159")


class TestCreateSyncLine(unittest.TestCase):

    def _run(self, frappe_mock, doc_data=None):
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            return ds.create_sync_line("LOG-1", doc_data or _doc_data())

    def test_crea_linea_nueva_con_name_prefijado(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = False
        frappe_mock.get_all.return_value = []

        line = MagicMock()
        frappe_mock.new_doc.return_value = line

        self._run(frappe_mock)

        frappe_mock.new_doc.assert_called_once_with("qp_SP_DocumentSyncLine")
        line.insert.assert_called_once_with(ignore_permissions=True)

    def test_reutiliza_linea_prefijada_existente(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = True
        existing = MagicMock()
        frappe_mock.get_doc.return_value = existing

        self._run(frappe_mock)

        frappe_mock.get_doc.assert_called_once_with(
            "qp_SP_DocumentSyncLine", "900162414:SETT0501159"
        )
        existing.save.assert_called_once_with(ignore_permissions=True)
        frappe_mock.new_doc.assert_not_called()

    def test_reutiliza_linea_legacy_mismo_proveedor(self):
        """Si existe una linea con name = nvfac_nume (formato legacy) del mismo
        proveedor, se reutiliza en vez de duplicarla con prefijo."""
        frappe_mock = MagicMock()
        # 1er exists (name prefijado) -> False; luego _get_existing_sync_line lo
        # encuentra por (nvpro_ndoc, nvfac_nume).
        frappe_mock.db.exists.side_effect = lambda doctype, name: name == "SETT0501159"
        frappe_mock.get_all.return_value = ["SETT0501159"]
        existing = MagicMock()
        frappe_mock.get_doc.return_value = existing

        self._run(frappe_mock)

        frappe_mock.get_doc.assert_called_once_with(
            "qp_SP_DocumentSyncLine", "SETT0501159"
        )
        existing.save.assert_called_once_with(ignore_permissions=True)
        frappe_mock.new_doc.assert_not_called()

    def test_no_reutiliza_linea_de_otro_proveedor(self):
        """Lineas de otro proveedor con el mismo nvfac_nume no se reutilizan."""
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = False
        frappe_mock.get_all.return_value = []
        line = MagicMock()
        frappe_mock.new_doc.return_value = line

        self._run(frappe_mock)

        frappe_mock.new_doc.assert_called_once_with("qp_SP_DocumentSyncLine")
        line.insert.assert_called_once_with(ignore_permissions=True)


class TestCreateDocumentDetailUpdate(unittest.TestCase):

    def test_rama_update_limpia_children_en_memoria(self):
        """Al re-sincronizar un detalle existente, los child rows cargados en
        memoria por get_doc se vacian antes de re-poblar, para que save() no
        valide links a File ya borrados."""
        frappe_mock = MagicMock()

        detail = MagicMock()
        detail.detail_lines = ["viejo_line"]
        detail.attached_files = ["viejo_attach"]
        detail.allowance_charges = ["viejo_ac"]
        frappe_mock.get_doc.return_value = detail
        frappe_mock.db.sql_list.return_value = ["file_id_1", "file_id_2"]

        doc_data = _doc_data()
        detail_name = ds._get_existing_detail_name = MagicMock(return_value="SETT0501146")

        with patch.dict(sys.modules, {"frappe": frappe_mock}), \
             patch.object(ds, "_get_existing_detail_name", return_value="SETT0501146"), \
             patch.object(ds, "create_detail_line",
                          side_effect=lambda item: MagicMock()):
            ds.create_document_detail(
                "900162414:SETT0501146", doc_data, []
            )

        self.assertEqual(detail.detail_lines, [])
        self.assertEqual(detail.attached_files, [])
        self.assertEqual(detail.allowance_charges, [])
        detail.save.assert_called_once_with(ignore_permissions=True)


class TestResolveSyncState(unittest.TestCase):
    """El re-sync no debe retroceder estados locales que ya avanzaron el
    flujo (BCC/PA/A/R), aunque documenteme aun reporte V/E/T."""

    def test_avanzado_local_no_retrocede_con_origen_analisis(self):
        self.assertEqual(ds._resolve_sync_state("BCC", "V", None), "BCC")
        self.assertEqual(ds._resolve_sync_state("PA", "V", None), "PA")
        self.assertEqual(ds._resolve_sync_state("A", "V", None), "A")
        self.assertEqual(ds._resolve_sync_state("R", "V", None), "R")

    def test_origen_definitivo_prevalece(self):
        self.assertEqual(ds._resolve_sync_state("BCC", "A", None), "A")
        self.assertEqual(ds._resolve_sync_state("PA", "R", None), "R")

    def test_origen_con_ueve_prevalece(self):
        self.assertEqual(ds._resolve_sync_state("BCC", "V", "033"), "V")

    def test_sin_estado_avanzado_toma_origen(self):
        self.assertEqual(ds._resolve_sync_state("E", "V", None), "V")
        self.assertEqual(ds._resolve_sync_state("V", "E", None), "E")
        self.assertEqual(ds._resolve_sync_state(None, "V", None), "V")

    def test_toma_estado_local(self):
        doc = MagicMock()
        doc.get.side_effect = {"nvfac_esta": "BCC"}.get
        document_data = {
            "Nvfac_esta": "V",
            "Nvfac_ueve": None,
            "Nvfac_cont": 1,
        }
        ds._set_document_detail_fields(doc, document_data)
        self.assertEqual(doc.nvfac_esta, "BCC")

    def test_toma_estado_origen_sin_avance(self):
        doc = MagicMock()
        doc.get.side_effect = {"nvfac_esta": "E"}.get
        document_data = {
            "Nvfac_esta": "V",
            "Nvfac_ueve": None,
            "Nvfac_cont": 1,
        }
        ds._set_document_detail_fields(doc, document_data)
        self.assertEqual(doc.nvfac_esta, "V")


if __name__ == "__main__":
    unittest.main()