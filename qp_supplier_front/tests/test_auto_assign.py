# -*- coding: utf-8 -*-
"""
test_auto_assign.py
===================
Pruebas unitarias para uses_cases/documenteme/auto_assign.py.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_assign.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.auto_assign import (
    auto_assign,
    is_inventariable_oc_type,
    resolve_assignee_emails,
    should_auto_assign,
)


class TestIsInventariableOCType(unittest.TestCase):

    OC_TYPE_ROWS = [
        {"oc_type": "01", "is_inventariable": 1},
        {"oc_type": "02", "is_inventariable": 1},
        {"oc_type": "03", "is_inventariable": 0},
        {"oc_type": "04", "is_inventariable": 0},
    ]

    def test_oc_type_inventariable(self):
        self.assertTrue(is_inventariable_oc_type("01", self.OC_TYPE_ROWS))

    def test_oc_type_no_inventariable(self):
        self.assertFalse(is_inventariable_oc_type("03", self.OC_TYPE_ROWS))

    def test_oc_type_no_configurado_retorna_none(self):
        self.assertIsNone(is_inventariable_oc_type("99", self.OC_TYPE_ROWS))

    def test_sin_filas_retorna_none(self):
        self.assertIsNone(is_inventariable_oc_type("01", []))


class TestResolveAssigneeEmails(unittest.TestCase):

    OC_TYPE_ROWS = [
        {"oc_type": "01", "is_inventariable": 1},
        {"oc_type": "02", "is_inventariable": 1},
        {"oc_type": "03", "is_inventariable": 0},
        {"oc_type": "04", "is_inventariable": 0},
    ]

    ASSIGNMENT_ROWS = [
        {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com", "b@x.com"]},
        {"headquarter": "CAL", "oc_type": "01", "user_emails": ["e@x.com"]},
        {"headquarter": "BOG", "oc_type": "03", "user_emails": ["c@x.com"]},
        {"headquarter": None, "oc_type": "04", "user_emails": ["d@x.com"]},
    ]

    def test_inventariable_busca_par_exacto_sede(self):
        emails = resolve_assignee_emails("01", "BOG", self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS)
        self.assertEqual(emails, ["a@x.com", "b@x.com"])

    def test_inventariable_tipo_con_varias_sedes_elige_par_exacto(self):
        emails = resolve_assignee_emails("01", "CAL", self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS)
        self.assertEqual(emails, ["e@x.com"])

    def test_inventariable_sin_sede_configurada_retorna_vacio(self):
        emails = resolve_assignee_emails("02", "CAL", self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS)
        self.assertEqual(emails, [])

    def test_no_inventariable_busca_por_oc_type(self):
        emails = resolve_assignee_emails("03", "BOG", self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS)
        self.assertEqual(emails, ["c@x.com"])

    def test_no_inventariable_ignora_sede_de_la_fila(self):
        emails = resolve_assignee_emails("03", "CAL", self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS)
        self.assertEqual(emails, ["c@x.com"])

    def test_oc_type_no_inventariable_sin_config_retorna_vacio(self):
        emails = resolve_assignee_emails("02", "CAL", self.OC_TYPE_ROWS, [])
        self.assertEqual(emails, [])

    def test_oc_type_sin_registrar_retorna_none(self):
        emails = resolve_assignee_emails("99", "BOG", self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS)
        self.assertIsNone(emails)

    def test_dedupe_emails_repetidos(self):
        rows = [
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com", "b@x.com"]},
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com"]},
        ]
        emails = resolve_assignee_emails("01", "BOG", self.OC_TYPE_ROWS, rows)
        self.assertEqual(emails, ["a@x.com", "b@x.com"])


class TestShouldAutoAssign(unittest.TestCase):

    def _invoice(self, **overrides):
        data = {
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "receipt_total": 400,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }
        data.update(overrides)
        return data

    def test_cumple_condicion(self):
        self.assertTrue(should_auto_assign(self._invoice()))

    def test_sin_orden_de_compra(self):
        self.assertFalse(should_auto_assign(self._invoice(nvfac_orde=None)))

    def test_sin_recibos(self):
        self.assertTrue(should_auto_assign(self._invoice(receipt_total=None)))

    def test_recepciones_cubren_total_no_asigna(self):
        self.assertFalse(should_auto_assign(self._invoice(receipt_total=1000)))

    def test_recepciones_mayores_al_total_asigna(self):
        self.assertTrue(should_auto_assign(self._invoice(receipt_total=1200)))

    def test_ya_asignada(self):
        self.assertFalse(should_auto_assign(self._invoice(assigned_to="admin@x.com")))

    def test_ya_asignada_multiple(self):
        self.assertFalse(should_auto_assign(self._invoice(has_assigned_users=True)))

    def test_fuera_de_cola(self):
        self.assertFalse(should_auto_assign(self._invoice(in_queue=False)))


class TestAutoAssignOrchestration(unittest.TestCase):

    def _callbacks(self, oc_context, receipt_total, emails, users, candidates):
        calls = []

        def candidates_fn():
            return list(candidates)

        def get_oc_context_fn(purchase_order_number):
            return oc_context

        def get_receipt_total_fn(purchase_order_number):
            return receipt_total

        def resolve_emails_fn(oc_type, headquarter):
            return emails

        def resolve_users_fn(resolved_emails):
            return users

        def add_assignees_fn(sync_line_name, assignees):
            calls.append((sync_line_name, list(assignees)))

        return calls, {
            "candidates_fn": candidates_fn,
            "get_oc_context_fn": get_oc_context_fn,
            "get_receipt_total_fn": get_receipt_total_fn,
            "resolve_emails_fn": resolve_emails_fn,
            "resolve_users_fn": resolve_users_fn,
            "add_assignees_fn": add_assignees_fn,
        }

    def test_asigna_cuando_cumple_condicion(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context={"oc_type": "01", "headquarter": "BOG"},
            receipt_total=400,
            emails=["a@x.com", "b@x.com"],
            users=["a@x.com", "b@x.com"],
            candidates=candidates,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(calls, [("FAC001", ["a@x.com", "b@x.com"])])

    def test_asigna_sin_recibo_de_compra(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context={"oc_type": "01", "headquarter": "BOG"},
            receipt_total=None,
            emails=["a@x.com", "b@x.com"],
            users=["a@x.com", "b@x.com"],
            candidates=candidates,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(calls, [("FAC001", ["a@x.com", "b@x.com"])])

    def test_sin_usuarios_resueltos_no_asigna(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context={"oc_type": "01", "headquarter": "BOG"},
            receipt_total=400,
            emails=["a@x.com"],
            users=[],
            candidates=candidates,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])

    def test_sin_oc_contexto_no_asigna(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context=None,
            receipt_total=400,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])

    def test_ya_asignada_no_se_reescribe(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "assigned_to": "admin@x.com",
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context={"oc_type": "01", "headquarter": "BOG"},
            receipt_total=400,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
