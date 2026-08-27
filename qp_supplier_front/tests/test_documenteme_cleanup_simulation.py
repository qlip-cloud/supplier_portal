# -*- coding: utf-8 -*-
"""
test_documenteme_cleanup_simulation.py
======================================
Pruebas unitarias para la limpieza manual de datos simulados
(resources/documenteme/cleanup_simulation.py).

Frappe se inyecta en sys.modules como mock (sin base de datos) y el módulo
bajo prueba se parchea objeto a objeto.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_documenteme_cleanup_simulation.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import cleanup_simulation as cleanup  # noqa: E402
from qp_supplier_front.resources.documenteme import simulation  # noqa: E402


def _make_frappe_mock():
    frappe_mock = MagicMock()
    return frappe_mock


class TestRunCleanup(unittest.TestCase):

    def test_borra_filas_simuladas_en_todos_los_doctypes(self):
        frappe_mock = _make_frappe_mock()
        documented_names = ["999999999:FAC-1"]
        line_names = ["999999999:FAC-1"]
        log_names = ["LOG-1"]
        pi_names = ["SIMFAC-1"]
        bc_names = ["SIMFAC-1"]

        def get_all_side_effect(doctype, filters=None, pluck=None, **kwargs):
            if doctype == cleanup.DOCUMENT_DETAIL:
                return list(documented_names)
            if doctype == cleanup.SYNC_LINE:
                return list(line_names)
            if doctype == cleanup.SYNC_LOG:
                return list(log_names)
            if doctype == cleanup.PURCHASE_INVOICE_BC:
                return list(bc_names)
            if doctype == cleanup.PURCHASE_INVOICE:
                return list(pi_names)
            return []

        frappe_mock.get_all.side_effect = get_all_side_effect
        frappe_mock.db.sql_list.return_value = ["FILE-1", "FILE-2"]

        with patch.object(cleanup, "frappe", frappe_mock):
            cleanup._run_cleanup()

        # Files borrados antes de los padres
        frappe_mock.delete_doc.assert_any_call(
            "File", "FILE-1", ignore_permissions=True, force=True
        )
        frappe_mock.delete_doc.assert_any_call(
            "File", "FILE-2", ignore_permissions=True, force=True
        )
        frappe_mock.delete_doc.assert_any_call(
            cleanup.DOCUMENT_DETAIL, "999999999:FAC-1",
            ignore_permissions=True, force=True,
        )
        frappe_mock.delete_doc.assert_any_call(
            cleanup.SYNC_LINE, "999999999:FAC-1",
            ignore_permissions=True, force=True,
        )
        frappe_mock.delete_doc.assert_any_call(
            cleanup.SYNC_LOG, "LOG-1", ignore_permissions=True, force=True
        )
        frappe_mock.delete_doc.assert_any_call(
            cleanup.PURCHASE_INVOICE, "SIMFAC-1",
            ignore_permissions=True, force=True,
        )
        frappe_mock.delete_doc.assert_any_call(
            cleanup.PURCHASE_INVOICE_BC, "SIMFAC-1",
            ignore_permissions=True, force=True,
        )

    def test_contadores_devueltos_por_doctype(self):
        frappe_mock = _make_frappe_mock()

        def get_all_side_effect(doctype, filters=None, pluck=None, **kwargs):
            if doctype == cleanup.DOCUMENT_DETAIL:
                return ["999999999:FAC-1", "999999999:FAC-2"]
            if doctype == cleanup.SYNC_LINE:
                return ["999999999:FAC-1"]
            if doctype == cleanup.SYNC_LOG:
                return ["LOG-1"]
            if doctype == cleanup.PURCHASE_INVOICE_BC:
                return ["SIMFAC-1", "SIMFAC-2"]
            if doctype == cleanup.PURCHASE_INVOICE:
                return ["SIMFAC-1", "SIMFAC-2", "SIMFAC-3"]
            return []

        frappe_mock.get_all.side_effect = get_all_side_effect
        frappe_mock.db.sql_list.return_value = []

        with patch.object(cleanup, "frappe", frappe_mock):
            deleted = cleanup._run_cleanup()

        self.assertEqual(deleted["document_details"], 2)
        self.assertEqual(deleted["sync_lines"], 1)
        self.assertEqual(deleted["sync_logs"], 1)
        self.assertEqual(deleted["purchase_invoices"], 3)
        self.assertEqual(deleted["purchase_invoice_bc"], 2)

    def test_idempotente_sin_datos(self):
        frappe_mock = _make_frappe_mock()
        frappe_mock.get_all.return_value = []
        frappe_mock.db.sql_list.return_value = []

        with patch.object(cleanup, "frappe", frappe_mock):
            deleted = cleanup._run_cleanup()

        self.assertEqual(deleted["document_details"], 0)
        self.assertEqual(deleted["sync_lines"], 0)
        self.assertEqual(deleted["sync_logs"], 0)
        self.assertEqual(deleted["purchase_invoices"], 0)
        self.assertEqual(deleted["purchase_invoice_bc"], 0)
        frappe_mock.delete_doc.assert_not_called()

    def test_filtros_por_convencion_nit_sim(self):
        frappe_mock = _make_frappe_mock()
        frappe_mock.get_all.return_value = []
        frappe_mock.db.sql_list.return_value = []

        with patch.object(cleanup, "frappe", frappe_mock):
            cleanup._run_cleanup()

        filters_by_doctype = {}
        for call in frappe_mock.get_all.call_args_list:
            args, kwargs = call
            doctype = args[0]
            filters_by_doctype[doctype] = kwargs.get("filters")

        self.assertEqual(
            filters_by_doctype[cleanup.DOCUMENT_DETAIL]["nvpro_ndoc"],
            simulation.SIMULATED_COMPANY_TAX_ID,
        )
        self.assertEqual(
            filters_by_doctype[cleanup.SYNC_LINE]["nvpro_ndoc"],
            simulation.SIMULATED_COMPANY_TAX_ID,
        )
        self.assertEqual(
            filters_by_doctype[cleanup.SYNC_LOG]["tax_id"],
            simulation.SIMULATED_COMPANY_TAX_ID,
        )
        self.assertEqual(
            filters_by_doctype[cleanup.PURCHASE_INVOICE]["invoice_id"],
            ["like", "SIM-%"],
        )
        self.assertEqual(
            filters_by_doctype[cleanup.PURCHASE_INVOICE_BC]["invoice_id"],
            ["like", "SIM-%"],
        )

    def test_commit_al_final(self):
        frappe_mock = _make_frappe_mock()
        frappe_mock.get_all.return_value = []
        frappe_mock.db.sql_list.return_value = []

        with patch.object(cleanup, "frappe", frappe_mock):
            cleanup._run_cleanup()

        frappe_mock.db.commit.assert_called_once()


class TestCleanupWhitelist(unittest.TestCase):

    def test_endpoint_whitelisted_existe(self):
        # El endpoint esta decorado con @frappe.whitelist(); en el entorno de
        # prueba frappe es un MagicMock y la funcion real vive en _run_cleanup.
        self.assertTrue(hasattr(cleanup, "cleanup_simulated_data"))
        self.assertTrue(callable(cleanup._run_cleanup))


if __name__ == "__main__":
    unittest.main()