# -*- coding: utf-8 -*-
"""Regresiones de resources/documenteme/attachments.py (frappe mockeado).

Cubre: (1) filtro de asignacion igual al de la lista, (2) rechazo de carpetas
y Files privados ajenos, (3) SQL parametrizado, (4) idempotencia, (5) ruta de
simulacion, y (6) el mismo filtro en simulacion.

Ejecutar: python -m pytest qp_supplier_front/tests/test_invoice_attachments_resources.py -v
"""
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeFile(object):
    def __init__(self, name, file_name, file_url, is_private=0, is_folder=0,
                 owner="u1@example.com", exists=True):
        self._d = dict(name=name, file_name=file_name, file_url=file_url,
                       is_private=is_private, is_folder=is_folder, owner=owner)
        self._exists = exists

    def get(self, key, default=None):
        return self._d.get(key, default)

    def exists_on_disk(self):
        return self._exists


def make_frappe():
    frappe = types.ModuleType("frappe")
    frappe.session = types.SimpleNamespace(user="u1@example.com")
    frappe.response = {}
    frappe.sql_calls = []
    st = {"roles": [], "assigned": [], "accessible": True,
          "attachments": [], "files": {}}

    def get_all(doctype, filters=None, fields=None, pluck=None, limit=None,
                start=0, page_length=None, order_by=None, **kw):
        f = filters or {}
        if doctype == "qp_SP_DocumentDetail":
            if f.get("document_sync_line") == ["in", []] or not st["accessible"]:
                return []
            nm = f.get("name", "D1")
            return [nm] if pluck else [{"name": nm}]
        if doctype in ("qp_SP_SyncLineAssignedUser", "qp_SP_DocumentSyncLine"):
            key = "parent" if doctype.endswith("AssignedUser") else "name"
            return [{key: p} for p in st["assigned"]]
        if doctype == "qp_SP_DocumentAttach":
            return list(st["attachments"])
        return []

    def get_doc(doctype, name=None):
        if doctype == "File" and name in st["files"]:
            return st["files"][name]
        raise Exception("not found")

    def sql(query, params=None):
        frappe.sql_calls.append((str(query), params))
        return [[0]] if str(query).lstrip().upper().startswith("SELECT") else None

    frappe.get_roles = lambda user=None: list(st["roles"])
    frappe.get_all = get_all
    frappe.get_doc = get_doc
    frappe.generate_hash = lambda length=10: "HASH000001"
    frappe.get_traceback = lambda: "tb"
    frappe.log_error = lambda *a, **k: None
    frappe.db = types.SimpleNamespace(
        sql=sql,
        exists=lambda dt, nm: dt == "qp_SP_DocumentDetail" and nm != "ZZZ",
        get_value=lambda *a, **k: None, rollback=lambda: None,
        commit=lambda: None)
    frappe.whitelist = lambda *a, **k: (lambda fn: fn)
    return frappe, st


class Base(unittest.TestCase):
    def setUp(self):
        self.frappe, self.st = make_frappe()
        self.p = patch.dict(sys.modules, {
            "frappe": self.frappe,
            "frappe.utils": types.ModuleType("frappe.utils")})
        self.p.start()
        import qp_supplier_front.resources.response as resp
        import qp_supplier_front.resources.documenteme.attachments as mod
        importlib.reload(resp)
        self.att = importlib.reload(mod)
        self.frappe.response.clear()

    def tearDown(self):
        self.p.stop()

    def status(self):
        return (self.frappe.response.get("message") or {}).get("status")

    def data(self):
        return (self.frappe.response.get("message") or {}).get("data") or {}

    def real(self):
        return patch.object(self.att.runtime, "resolve", return_value={"data": None})

    def sim(self, facade):
        return patch.object(self.att.runtime, "resolve",
                            return_value={"data": facade})


class TestAccessControl(Base):
    def test_no_role_applies_assignment_filter_and_403(self):
        seen = {}

        def ga(doctype, **kw):
            if doctype == "qp_SP_DocumentDetail":
                seen.update(kw.get("filters") or {})
            return []

        orig = self.frappe.get_all
        self.frappe.get_all = ga
        with self.real():
            self.att.get_attachments("D1")
        self.frappe.get_all = orig
        self.assertEqual(self.status(), 403)
        self.assertEqual(seen.get("document_sync_line"), ["in", []])
        self.assertEqual(seen.get("name"), "D1")

    def test_restricted_roles_without_assignment_403(self):
        for role in ("Administrador Compras Documenteme",
                     "Administrador Sede Documenteme"):
            self.st["roles"] = [role]
            self.frappe.response.clear()
            with self.real():
                self.att.get_attachments("D1")
            self.assertEqual(self.status(), 403, role)

    def test_restricted_role_with_assignment_200(self):
        self.st["roles"] = ["Administrador Compras Documenteme"]
        self.st["assigned"] = ["L1"]
        with self.real():
            self.att.get_attachments("D1")
        self.assertEqual(self.status(), 200)

    def test_admin_200_and_empty_doc_400(self):
        self.st["roles"] = ["Administrador Documenteme"]
        with self.real():
            self.att.get_attachments("D1")
        self.assertEqual(self.status(), 200)
        self.frappe.response.clear()
        with self.real():
            self.att.get_attachments("")
        self.assertEqual(self.status(), 400)

    def test_add_attachment_requires_access(self):
        with self.real():
            self.att.add_attachment("D1", file_id="F1")
        self.assertEqual(self.status(), 403)


class TestCanUseFile(Base):
    def test_rules(self):
        self.assertFalse(self.att._can_use_file(
            FakeFile("F", "d", "/d", is_folder=1)))
        self.assertFalse(self.att._can_use_file(
            FakeFile("F", "s.pdf", "/s.pdf", is_private=1, owner="x@y.com")))
        self.assertTrue(self.att._can_use_file(
            FakeFile("F", "m.pdf", "/m.pdf", is_private=1, owner="u1@example.com")))
        self.assertTrue(self.att._can_use_file(
            FakeFile("F", "p.pdf", "/p.pdf", is_private=0, owner="x@y.com")))


class TestSqlSafety(Base):
    def test_insert_parameterized(self):
        payload = "D1'; DROP TABLE tabqp_SP_DocumentAttach; --"
        self.att._insert_attach_row(payload, {
            "file_name": "a.pdf", "file_type": "PDF",
            "file_url": "/files/a.pdf", "file_id": "F1"})
        inserts = [(q, p) for q, p in self.frappe.sql_calls if "INSERT" in q.upper()]
        self.assertEqual(len(inserts), 1)
        q, p = inserts[0]
        p = tuple(p)
        self.assertNotIn("DROP TABLE", q)
        self.assertIn(payload, p)
        self.assertEqual(q.count("%s"), len(p))
        self.assertNotIn("/files/a.pdf", q)


class TestSimulation(Base):
    def setUp(self):
        Base.setUp(self)
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        from qp_supplier_front.simulation.store import MemoryStore
        self.store = MemoryStore()
        self.store.insert("qp_SP_DocumentDetail", {
            "name": "D1", "document_sync_line": "L1"})
        self.facade = DataFacade(store=self.store)
        self.st["roles"] = ["Administrador Documenteme"]
        self.st["files"] = {
            "F_PDF": FakeFile("F_PDF", "factura.pdf", "/files/factura.pdf"),
            "F_FOLDER": FakeFile("F_FOLDER", "dir", "/files/dir", is_folder=1),
            "F_PRIV": FakeFile("F_PRIV", "s.pdf", "/files/s.pdf",
                               is_private=1, owner="x@y.com"),
        }

    def children(self):
        return len(self.store.query("qp_SP_DocumentAttach"))

    def test_folder_and_private_other_rejected(self):
        with self.sim(self.facade):
            for fid in ("F_FOLDER", "F_PRIV"):
                self.frappe.response.clear()
                self.att.add_attachment("D1", file_id=fid)
                self.assertEqual(self.status(), 403, fid)
        self.assertEqual(self.children(), 0)

    def test_idempotent_and_no_raw_sql_and_200(self):
        self.frappe.sql_calls[:] = []
        with self.sim(self.facade):
            for _ in range(2):
                self.frappe.response.clear()
                self.att.add_attachment("D1", file_id="F_PDF")
                self.assertEqual(self.status(), 200)
            self.frappe.response.clear()
            self.att.get_attachments("D1")
            self.assertEqual(self.status(), 200)
            self.assertTrue(self.data().get("has_downloadable"))
        self.assertEqual(self.children(), 1)
        self.assertEqual(
            [q for q, p in self.frappe.sql_calls if "INSERT" in q.upper()], [])

    def test_same_url_new_file_id_no_duplicate(self):
        with self.sim(self.facade):
            self.frappe.response.clear()
            self.att.add_attachment("D1", file_id="F_PDF")
            with patch.object(self.att, "_resolve_file", return_value=FakeFile(
                    "F_NEW", "factura.pdf", "/files/factura.pdf")):
                self.frappe.response.clear()
                self.att.add_attachment("D1", file_id="F_NEW")
        self.assertEqual(self.children(), 1)


class TestRealStatus(Base):
    def test_only_xml_and_missing_not_downloadable(self):
        self.st["roles"] = ["Administrador Documenteme"]
        self.st["files"] = {
            "F_OK": FakeFile("F_OK", "a.pdf", "/files/a.pdf", exists=True),
            "F_GONE": FakeFile("F_GONE", "b.pdf", "/files/b.pdf", exists=False),
        }
        self.st["attachments"] = [
            {"file_name": "a.xml", "file_type": "XML",
             "file_url": "/files/a.xml", "file_id": "F_OK"},
            {"file_name": "b.pdf", "file_type": "PDF",
             "file_url": "/files/b.pdf", "file_id": "F_GONE"},
        ]
        with self.real():
            self.att.get_attachments("D1")
        self.assertFalse(self.data().get("has_downloadable"))
        self.assertEqual(self.data().get("non_xml_count"), 1)
        self.st["attachments"].append(
            {"file_name": "c.pdf", "file_type": "PDF",
             "file_url": "/files/c.pdf", "file_id": "F_OK"})
        self.frappe.response.clear()
        with self.real():
            self.att.get_attachments("D1")
        self.assertTrue(self.data().get("has_downloadable"))


class TestSimulationAccessControl(Base):
    """La rama de simulacion debe aplicar el filtro de asignacion igual que la
    lista: un usuario restringido sin la factura asignada recibe 403."""

    def setUp(self):
        Base.setUp(self)
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        from qp_supplier_front.simulation.store import MemoryStore
        self.store = MemoryStore()
        self.store.insert("qp_SP_DocumentDetail", {
            "name": "D_SECRET", "document_sync_line": "L_SECRET"})
        self.facade = DataFacade(store=self.store)
        self.st["files"]["F_OK"] = FakeFile("F_OK", "x.pdf", "/files/x.pdf")

    def test_unassigned_restricted_user_blocked_in_simulation(self):
        self.st["roles"] = ["Administrador Sede Documenteme"]
        self.st["assigned"] = []
        with self.sim(self.facade):
            self.frappe.response.clear()
            self.att.get_attachments("D_SECRET")
            self.assertEqual(self.status(), 403, "sim get_attachments filter")
            self.frappe.response.clear()
            self.att.add_attachment("D_SECRET", file_id="F_OK")
            self.assertEqual(self.status(), 403, "sim add_attachment filter")
        self.assertEqual(len(self.store.query("qp_SP_DocumentAttach")), 0)

    def test_assigned_restricted_user_allowed_in_simulation(self):
        self.store.insert("qp_SP_SyncLineAssignedUser", {
            "name": "A1",
            "parent": "L_SECRET",
            "parenttype": "qp_SP_DocumentSyncLine",
            "user": "u1@example.com",
        })
        self.st["roles"] = ["Administrador Sede Documenteme"]
        with self.sim(self.facade):
            self.frappe.response.clear()
            self.att.get_attachments("D_SECRET")
            self.assertEqual(self.status(), 200, "sim assigned user")
            self.frappe.response.clear()
            self.att.add_attachment("D_SECRET", file_id="F_OK")
            self.assertEqual(self.status(), 200, "sim assigned add")
        self.assertEqual(len(self.store.query("qp_SP_DocumentAttach")), 1)


if __name__ == "__main__":
    unittest.main()
