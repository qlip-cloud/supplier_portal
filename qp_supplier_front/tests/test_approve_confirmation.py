# -*- coding: utf-8 -*-
"""
test_approve_confirmation.py
============================
Pruebas unitarias para uses_cases/documenteme/approve_confirmation.py.

Completamente aisladas de Frappe y la base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_approve_confirmation.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.approve_confirmation import (
    validate_confirmation,
    is_approval_candidate,
    process_confirmation,
    is_approval_successful,
)


class TestValidateConfirmation(unittest.TestCase):

    def test_ok_con_ambos_parametros(self):
        self.assertEqual(validate_confirmation("123", "ABC"), [])

    def test_falta_invoice_id(self):
        self.assertIn("invoice_id", validate_confirmation("", "ABC")[0])

    def test_falta_confirmation_id(self):
        self.assertIn("confirmation_id", validate_confirmation("123", "")[0])

    def test_faltan_ambos(self):
        errors = validate_confirmation(" ", None)
        self.assertEqual(len(errors), 2)

    def test_limpia_espacios(self):
        self.assertEqual(validate_confirmation("  123  ", "  ABC "), [])


class TestIsApprovalCandidate(unittest.TestCase):

    def test_bcc_es_candidato(self):
        self.assertTrue(is_approval_candidate("BCC"))

    def test_pa_es_candidato(self):
        self.assertTrue(is_approval_candidate("PA"))

    def test_aprobado_no_es_candidato(self):
        self.assertFalse(is_approval_candidate("A"))

    def test_none_no_es_candidato(self):
        self.assertFalse(is_approval_candidate(None))


class TestProcessConfirmation(unittest.TestCase):

    def _callbacks(self, doc=None):
        calls = {
            "find": [],
            "set": [],
            "mark": [],
            "enqueue": [],
            "commit": [],
        }
        doc = doc or {"name": "FAC001", "invoice_id": "123"}

        def find(invoice_id):
            calls["find"].append(invoice_id)
            return doc

        def set_cf(doc, confirmation_id):
            calls["set"].append((doc["invoice_id"], confirmation_id))

        def mark(doc):
            calls["mark"].append(doc["name"])

        def enqueue(doc):
            calls["enqueue"].append(doc["name"])

        def commit():
            calls["commit"].append(True)

        return doc, find, set_cf, mark, enqueue, commit, calls

    def test_procesa_confirmacion_exitosa(self):
        doc, find, set_cf, mark, enqueue, commit, calls = self._callbacks()
        result = process_confirmation(
            "123", "ABC", find, set_cf, mark, enqueue, commit
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["doc"], doc)
        self.assertEqual(calls["find"], ["123"])
        self.assertEqual(calls["set"], [("123", "ABC")])
        self.assertEqual(calls["mark"], ["FAC001"])
        self.assertEqual(calls["enqueue"], ["FAC001"])
        self.assertEqual(calls["commit"], [True])

    def test_falla_si_faltan_parametros(self):
        doc, find, set_cf, mark, enqueue, commit, calls = self._callbacks()
        result = process_confirmation(
            "", "", find, set_cf, mark, enqueue, commit
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["errors"])
        self.assertEqual(calls["find"], [])

    def test_falla_si_no_se_encuentra_documento(self):
        doc, find, set_cf, mark, enqueue, commit, calls = self._callbacks(None)

        def find(invoice_id):
            calls["find"].append(invoice_id)
            return None

        result = process_confirmation(
            "999", "ABC", find, set_cf, mark, enqueue, commit
        )
        self.assertFalse(result["ok"])
        self.assertIn("999", result["errors"][0])
        self.assertEqual(calls["set"], [])
        self.assertEqual(calls["mark"], [])
        self.assertEqual(calls["enqueue"], [])


class TestIsApprovalSuccessful(unittest.TestCase):

    def test_aprobado_con_033(self):
        def last_event(invoice_id):
            return "033"
        self.assertTrue(is_approval_successful("1", last_event))

    def test_no_aprobado_con_otro_evento(self):
        def last_event(invoice_id):
            return "031"
        self.assertFalse(is_approval_successful("1", last_event))

    def test_no_aprobado_sin_evento(self):
        def last_event(invoice_id):
            return None
        self.assertFalse(is_approval_successful("1", last_event))


if __name__ == "__main__":
    unittest.main()
