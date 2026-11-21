# -*- coding: utf-8 -*-
"""
test_documenteme_assign.py
==========================
Pruebas unitarias para uses_cases/documenteme/assign.py.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_documenteme_assign.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.assign import assign_documents


class _FakeLine(object):

    def __init__(self, name, assigned_to=None, assigned_users=None):
        self.name = name
        self.assigned_to = assigned_to
        self.assigned_users = list(assigned_users or [])
        self.saved = 0

    def set(self, fieldname, value):
        if fieldname == "assigned_users":
            self.assigned_users = list(value)
            return
        setattr(self, fieldname, value)


class _FakeStore(object):

    def __init__(self, lines):
        self.lines = {line.name: line for line in lines}
        self.saved = []

    def get_doc(self, doctype, name):
        return self.lines[name]

    def save(self, doc):
        doc.saved += 1
        self.saved.append(doc.name)


class TestAssignDocuments(unittest.TestCase):

    def _run(self, line_names, users, lines):
        store = _FakeStore(lines)
        result = assign_documents(
            line_names, users, store.get_doc, store.save)
        return result, store

    def test_asigna_varios_usuarios_en_assigned_users(self):
        line = _FakeLine("SL-1")

        result, store = self._run(
            ["SL-1"], ["a@x.com", "b@x.com"], [line])

        self.assertEqual(
            ["a@x.com", "b@x.com"],
            [row.get("user") for row in line.assigned_users],
        )
        self.assertEqual(["a@x.com", "b@x.com"], result)
        self.assertEqual(1, line.saved)

    def test_limpia_assigned_to_legacy(self):
        line = _FakeLine("SL-1", assigned_to="viejo@x.com")

        self._run(["SL-1"], ["nuevo@x.com"], [line])

        self.assertIsNone(line.assigned_to)
        self.assertEqual(
            ["nuevo@x.com"],
            [row.get("user") for row in line.assigned_users],
        )

    def test_reemplaza_la_lista_anterior(self):
        line = _FakeLine(
            "SL-1",
            assigned_users=[{"user": "viejo1@x.com"}, {"user": "viejo2@x.com"}],
        )

        self._run(["SL-1"], ["nuevo@x.com"], [line])

        self.assertEqual(
            ["nuevo@x.com"],
            [row.get("user") for row in line.assigned_users],
        )

    def test_deduplica_usuarios_y_descarta_vacios(self):
        line = _FakeLine("SL-1")

        self._run(
            ["SL-1"],
            ["a@x.com", None, "", "a@x.com", "b@x.com"],
            [line],
        )

        self.assertEqual(
            ["a@x.com", "b@x.com"],
            [row.get("user") for row in line.assigned_users],
        )

    def test_asigna_a_varias_sync_lines(self):
        line_a = _FakeLine("SL-1")
        line_b = _FakeLine("SL-2")

        self._run(["SL-1", "SL-2"], ["a@x.com"], [line_a, line_b])

        self.assertEqual(
            ["a@x.com"],
            [row.get("user") for row in line_a.assigned_users],
        )
        self.assertEqual(
            ["a@x.com"],
            [row.get("user") for row in line_b.assigned_users],
        )


if __name__ == "__main__":
    unittest.main()
