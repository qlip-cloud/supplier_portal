# -*- coding: utf-8 -*-
"""
test_simulation_store.py
========================
Pruebas del almacen en memoria del modo simulacion documenteme
(simulation/store.py). Sin dependencias de Frappe ni base de datos.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_simulation_store.py -v
"""
import unittest

from qp_supplier_front.simulation.store import MemoryStore


def _doc(name="DOC1", estado="E", ueve=None, total=100, cont="1"):
    return {"name": name, "nvfac_esta": estado, "nvfac_ueve": ueve,
            "nvfac_totp": total, "nvfac_cont": cont}


class TestInsertGetDelete(unittest.TestCase):

    def test_insert_con_name(self):
        store = MemoryStore()
        name = store.insert("qp_SP_DocumentDetail", _doc())
        self.assertEqual(name, "DOC1")
        self.assertEqual(store.get("qp_SP_DocumentDetail", "DOC1")["nvfac_esta"], "E")

    def test_insert_autoname(self):
        store = MemoryStore()
        name = store.insert("qp_SP_DocumentDetail", {"nvfac_nume": "F"})
        self.assertTrue(name)

    def test_get_devuelve_copia(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        row = store.get("qp_SP_DocumentDetail", "DOC1")
        row["nvfac_esta"] = "R"
        self.assertEqual(store.get("qp_SP_DocumentDetail", "DOC1")["nvfac_esta"], "E")

    def test_get_inexistente(self):
        self.assertIsNone(MemoryStore().get("qp_SP_DocumentDetail", "X"))

    def test_exists_por_nombre(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        self.assertTrue(store.exists("qp_SP_DocumentDetail", "DOC1"))
        self.assertFalse(store.exists("qp_SP_DocumentDetail", "X"))

    def test_exists_por_filtros(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(estado="E"))
        self.assertTrue(store.exists(
            "qp_SP_DocumentDetail", {"nvfac_esta": "E"}))
        self.assertFalse(store.exists(
            "qp_SP_DocumentDetail", {"nvfac_esta": "R"}))

    def test_delete(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        store.delete("qp_SP_DocumentDetail", "DOC1")
        self.assertFalse(store.exists("qp_SP_DocumentDetail", "DOC1"))

    def test_has_doctype(self):
        store = MemoryStore()
        self.assertFalse(store.has_doctype("qp_SP_DocumentDetail"))
        store.insert("qp_SP_DocumentDetail", _doc())
        self.assertTrue(store.has_doctype("qp_SP_DocumentDetail"))


class TestUpdateSetGetValue(unittest.TestCase):

    def test_update_mezcla(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        store.update("qp_SP_DocumentDetail", "DOC1", {"nvfac_esta": "V"})
        row = store.get("qp_SP_DocumentDetail", "DOC1")
        self.assertEqual(row["nvfac_esta"], "V")
        self.assertEqual(row["name"], "DOC1")

    def test_update_inexistente(self):
        self.assertIsNone(MemoryStore().update("qp_SP_DocumentDetail", "X", {}))

    def test_set_value_por_nombre(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        store.set_value("qp_SP_DocumentDetail", "DOC1", "nvfac_esta", "R")
        self.assertEqual(store.get("qp_SP_DocumentDetail", "DOC1")["nvfac_esta"], "R")

    def test_set_value_por_filtros_multiples(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(name="D1"))
        store.insert("qp_SP_DocumentDetail", _doc(name="D2"))
        count = store.set_value(
            "qp_SP_DocumentDetail", {"nvfac_esta": "E"}, "nvfac_esta", "V")
        self.assertEqual(count, 2)

    def test_get_value_por_nombre(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(total=250))
        self.assertEqual(store.get_value("qp_SP_DocumentDetail", "DOC1", "nvfac_totp"), 250)

    def test_get_value_por_filtros(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(name="D1"))
        store.insert("qp_SP_DocumentDetail", _doc(name="D2", total=999))
        self.assertEqual(
            store.get_value("qp_SP_DocumentDetail",
                            {"nvfac_totp": 999}, "name"), "D2")

    def test_get_value_filtro_vacio(self):
        store = MemoryStore()
        self.assertIsNone(
            store.get_value("qp_SP_DocumentDetail",
                            {"nvfac_totp": 999}, "name"))

    def test_get_value_sin_campo(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        row = store.get_value("qp_SP_DocumentDetail", "DOC1")
        self.assertEqual(row["name"], "DOC1")


class TestQueryFilters(unittest.TestCase):

    def _store(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(name="D1", estado="E", ueve="", total=100))
        store.insert("qp_SP_DocumentDetail", _doc(name="D2", estado="V", ueve=None, total=200))
        store.insert("qp_SP_DocumentDetail", _doc(name="D3", estado="R", ueve="031", total=300))
        return store

    def test_igualdad(self):
        rows = self._store().query("qp_SP_DocumentDetail",
                                   filters={"nvfac_esta": "E"})
        self.assertEqual([r["name"] for r in rows], ["D1"])

    def test_in(self):
        rows = self._store().query("qp_SP_DocumentDetail",
                                   filters={"nvfac_esta": ["in", ["E", "V"]]})
        self.assertCountEqual([r["name"] for r in rows], ["D1", "D2"])

    def test_is_not_set(self):
        rows = self._store().query("qp_SP_DocumentDetail",
                                   filters={"nvfac_ueve": ["is", "not set"]})
        # D1 ueve="" y D2 ueve=None son "not set" (semantica Frappe)
        self.assertCountEqual([r["name"] for r in rows], ["D1", "D2"])

    def test_like(self):
        rows = self._store().query("qp_SP_DocumentDetail",
                                   filters={"name": ["like", "D%"]})
        self.assertEqual(len(rows), 3)

    def test_comparativo(self):
        rows = self._store().query("qp_SP_DocumentDetail",
                                   filters={"nvfac_totp": [">", 150]})
        self.assertEqual([r["name"] for r in rows], ["D2", "D3"])

    def test_sin_filtros_devuelve_todo(self):
        self.assertEqual(len(self._store().query("qp_SP_DocumentDetail")), 3)

    def test_filtro_sin_match(self):
        self.assertEqual(
            self._store().query("qp_SP_DocumentDetail",
                                filters={"nvfac_esta": "X"}), [])


class TestQueryOrderPagination(unittest.TestCase):

    def _store(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(name="D1", total=100))
        store.insert("qp_SP_DocumentDetail", _doc(name="D2", total=300))
        store.insert("qp_SP_DocumentDetail", _doc(name="D3", total=200))
        return store

    def test_order_desc(self):
        rows = self._store().query(
            "qp_SP_DocumentDetail", order_by="nvfac_totp desc")
        self.assertEqual([r["name"] for r in rows], ["D2", "D3", "D1"])

    def test_order_asc_con_nombre(self):
        rows = self._store().query(
            "qp_SP_DocumentDetail", order_by="nvfac_totp asc, name desc")
        self.assertEqual([r["name"] for r in rows], ["D1", "D3", "D2"])

    def test_paginacion(self):
        rows = self._store().query(
            "qp_SP_DocumentDetail", order_by="name asc", start=1, page_length=1)
        self.assertEqual([r["name"] for r in rows], ["D2"])

    def test_start_sin_pagina(self):
        rows = self._store().query(
            "qp_SP_DocumentDetail", order_by="name asc", start=2)
        self.assertEqual([r["name"] for r in rows], ["D3"])

    def test_limit(self):
        rows = self._store().query(
            "qp_SP_DocumentDetail", order_by="name asc", limit=2)
        self.assertEqual([r["name"] for r in rows], ["D1", "D2"])

    def test_pluck(self):
        values = self._store().query(
            "qp_SP_DocumentDetail", order_by="name asc", pluck="nvfac_totp")
        self.assertEqual(values, [100, 300, 200])

    def test_fields_subconjunto(self):
        rows = self._store().query(
            "qp_SP_DocumentDetail", fields=["name", "nvfac_esta"])
        for row in rows:
            self.assertEqual(set(row.keys()), {"name", "nvfac_esta"})

    def test_fields_star(self):
        rows = self._store().query("qp_SP_DocumentDetail", fields=["*"])
        self.assertEqual(len(rows), 3)


class TestChildTables(unittest.TestCase):

    def test_child_rows_por_parent(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(name="DOC1"))
        store.insert("qp_SP_DetailLine", {"parent": "DOC1", "nvdet_cont": "1"}, name="L1")
        rows = store.query("qp_SP_DetailLine", filters={"parent": "DOC1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "L1")

    def test_count(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc(name="D1", estado="E"))
        store.insert("qp_SP_DocumentDetail", _doc(name="D2", estado="E"))
        store.insert("qp_SP_DocumentDetail", _doc(name="D3", estado="R"))
        self.assertEqual(
            store.count("qp_SP_DocumentDetail", {"nvfac_esta": "E"}), 2)

    def test_all_doctypes(self):
        store = MemoryStore()
        store.insert("qp_SP_DocumentDetail", _doc())
        store.insert("qp_SP_DocumentSyncLine", {"name": "SL1"})
        self.assertEqual(
            store.all_doctypes(),
            ["qp_SP_DocumentDetail", "qp_SP_DocumentSyncLine"])


if __name__ == "__main__":
    unittest.main()