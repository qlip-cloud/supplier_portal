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

    def test_catch_all_para_contado_sin_oc(self):
        rows = [
            {"headquarter": "", "oc_type": "", "user_emails": ["a@x.com", "b@x.com"]},
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["c@x.com"]},
        ]
        emails = resolve_assignee_emails(None, None, self.OC_TYPE_ROWS, rows)
        self.assertEqual(emails, ["a@x.com", "b@x.com"])

    def test_catch_all_sin_fila_retorna_vacio(self):
        emails = resolve_assignee_emails(
            None, None, self.OC_TYPE_ROWS, self.ASSIGNMENT_ROWS
        )
        self.assertEqual(emails, [])

    def test_wildcard_no_aplica_asigna_sin_importar_oc_ni_sede(self):
        rows = [
            {"headquarter": "", "oc_type": "No aplica", "user_emails": ["w@x.com"]},
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com"]},
        ]
        # No inventariable sin config exacta -> solo wildcard.
        self.assertEqual(
            resolve_assignee_emails("03", "CAL", self.OC_TYPE_ROWS, rows),
            ["w@x.com"],
        )
        # Inventariable sin par exacto (sede inexistente).
        self.assertEqual(
            resolve_assignee_emails("01", "CAL", self.OC_TYPE_ROWS, rows),
            ["w@x.com"],
        )
        # OC type no registrado.
        self.assertEqual(
            resolve_assignee_emails("99", "BOG", self.OC_TYPE_ROWS, rows),
            ["w@x.com"],
        )
        # Contado sin OC.
        self.assertEqual(
            resolve_assignee_emails(None, None, self.OC_TYPE_ROWS, rows),
            ["w@x.com"],
        )

    def test_wildcard_se_suma_al_match_exacto(self):
        rows = [
            {"headquarter": "", "oc_type": "No aplica", "user_emails": ["w@x.com"]},
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com"]},
        ]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", self.OC_TYPE_ROWS, rows),
            ["a@x.com", "w@x.com"],
        )

    def test_roles_se_expanden_via_callback_solo_de_la_fila_match(self):
        rows = [
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com"],
             "user_roles": ["Alpla Compras"]},
            {"headquarter": "BOG", "oc_type": "03", "user_emails": ["c@x.com"],
             "user_roles": ["Alpla Finanzas"]},
        ]
        requested = []

        def roles_to_users_fn(roles):
            requested.append(list(roles))
            return ["a@x.com", "rol@x.com"]

        emails = resolve_assignee_emails(
            "01", "BOG", self.OC_TYPE_ROWS, rows, roles_to_users_fn
        )

        self.assertEqual(emails, ["a@x.com", "rol@x.com"])
        self.assertEqual(requested, [["Alpla Compras"]])

    def test_usuario_en_email_y_rol_se_asigna_una_vez(self):
        rows = [
            {"headquarter": "BOG", "oc_type": "01", "user_emails": ["rol@x.com"],
             "user_roles": ["Alpla Compras"]},
        ]
        emails = resolve_assignee_emails(
            "01",
            "BOG",
            self.OC_TYPE_ROWS,
            rows,
            lambda roles: ["rol@x.com", "otro@x.com"],
        )
        self.assertEqual(emails, ["rol@x.com", "otro@x.com"])

    def test_wildcard_roles_aplican_al_contado_sin_oc(self):
        rows = [
            {"headquarter": "CAL", "oc_type": "No aplica", "user_emails": [],
             "user_roles": ["Alpla Soporte"]},
        ]
        emails = resolve_assignee_emails(
            None, None, self.OC_TYPE_ROWS, rows, lambda roles: ["s@x.com"]
        )
        self.assertEqual(emails, ["s@x.com"])

    def test_sin_callback_sin_roles_mantiene_comportamiento(self):
        rows = [
            {"headquarter": "", "oc_type": "", "user_emails": ["a@x.com"],
             "user_roles": ["Alpla Finanzas"]},
        ]
        emails = resolve_assignee_emails(None, None, self.OC_TYPE_ROWS, rows)
        self.assertEqual(emails, ["a@x.com"])


class TestShouldAutoAssign(unittest.TestCase):

    def _invoice(self, **overrides):
        data = {
            "nvfac_nume": "FAC001",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }
        data.update(overrides)
        return data

    def _bank(self, amount):
        return [{"name": "R1", "amount": amount, "date": "2026-01-01", "qp_invoice": None}]

    def test_cumple_condicion(self):
        self.assertTrue(should_auto_assign(self._invoice(), self._bank(400)))

    def test_sin_orden_de_compra(self):
        self.assertFalse(should_auto_assign(self._invoice(nvfac_orde=None), self._bank(400)))

    def test_sin_recibos(self):
        self.assertTrue(should_auto_assign(self._invoice(), []))

    def test_recepciones_cubren_total_no_asigna(self):
        self.assertFalse(should_auto_assign(self._invoice(), self._bank(1000)))

    def test_recepciones_mayores_al_total_asigna(self):
        self.assertTrue(should_auto_assign(self._invoice(), self._bank(1200)))

    def test_recepciones_consumidas_por_otra_factura_asigna(self):
        bank = [{"name": "R1", "amount": 1000, "date": "2026-01-01", "qp_invoice": "FAC000"}]
        self.assertTrue(should_auto_assign(self._invoice(), bank))

    def test_ya_asignada(self):
        self.assertFalse(should_auto_assign(self._invoice(assigned_to="admin@x.com"), self._bank(400)))

    def test_ya_asignada_multiple(self):
        self.assertFalse(should_auto_assign(self._invoice(has_assigned_users=True), self._bank(400)))

    def test_fuera_de_cola(self):
        self.assertFalse(should_auto_assign(self._invoice(in_queue=False), self._bank(400)))


class TestAutoAssignOrchestration(unittest.TestCase):

    def _callbacks(self, oc_context, receipt_bank, emails, users, candidates,
                   resolve_rule_fn=None, po_exists_fn=None):
        calls = []

        def candidates_fn():
            return list(candidates)

        def get_oc_context_fn(purchase_order_number):
            return oc_context

        def get_receipt_bank_fn(purchase_order_number):
            return receipt_bank

        def resolve_emails_fn(oc_type, headquarter):
            return emails

        def resolve_users_fn(resolved_emails):
            return users

        def add_assignees_fn(sync_line_name, assignees):
            calls.append((sync_line_name, list(assignees)))

        return calls, {
            "candidates_fn": candidates_fn,
            "get_oc_context_fn": get_oc_context_fn,
            "get_receipt_bank_fn": get_receipt_bank_fn,
            "resolve_emails_fn": resolve_emails_fn,
            "resolve_users_fn": resolve_users_fn,
            "add_assignees_fn": add_assignees_fn,
            "resolve_rule_fn": resolve_rule_fn,
            "po_exists_fn": po_exists_fn,
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
            receipt_bank=[{"name": "R1", "amount": 400, "date": "2026-01-01", "qp_invoice": None}],
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
            receipt_bank=[],
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
            receipt_bank=[{"name": "R1", "amount": 400, "date": "2026-01-01", "qp_invoice": None}],
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
            receipt_bank=[{"name": "R1", "amount": 400, "date": "2026-01-01", "qp_invoice": None}],
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
            receipt_bank=[{"name": "R1", "amount": 400, "date": "2026-01-01", "qp_invoice": None}],
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])

    def test_contado_sin_regla_no_se_asigna(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_conv": "1",
            "nvfac_orde": None,
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context=None,
            receipt_bank=None,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
            resolve_rule_fn=lambda doc: None,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])

    def test_contado_no_action_no_se_asigna(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_conv": "1",
            "nvfac_orde": None,
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context=None,
            receipt_bank=None,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
            resolve_rule_fn=lambda doc: {"rule_code": "no_action"},
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])

    def test_contado_rompe_regla_sin_oc_se_asigna_catch_all(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_conv": "1",
            "nvfac_orde": None,
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context=None,
            receipt_bank=None,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
            resolve_rule_fn=lambda doc: {"rule_code": "no_po"},
            po_exists_fn=lambda oc: bool(oc),
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(calls, [("FAC001", ["a@x.com"])])

    def test_contado_rompe_regla_no_receipt_con_oc_se_asigna(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_conv": "1",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context={"oc_type": "03", "headquarter": "BOG"},
            receipt_bank=None,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
            resolve_rule_fn=lambda doc: {"rule_code": "no_receipt"},
            po_exists_fn=lambda oc: bool(oc),
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(calls, [("FAC001", ["a@x.com"])])

    def test_contado_cumple_regla_no_po_con_oc_no_se_asigna(self):
        candidates = [{
            "nvfac_nume": "FAC001",
            "nvfac_conv": "1",
            "nvfac_orde": "OC001",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }]
        calls, callbacks = self._callbacks(
            oc_context={"oc_type": "03", "headquarter": "BOG"},
            receipt_bank=None,
            emails=["a@x.com"],
            users=["a@x.com"],
            candidates=candidates,
            resolve_rule_fn=lambda doc: {"rule_code": "no_po"},
            po_exists_fn=lambda oc: bool(oc),
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])

    def test_nota_credito_nunca_se_asigna(self):
        # NC (nvtip_docu == "C"): sin restriccion ni validacion, siempre se
        # aprueba. Aunque las condiciones de asignacion se cumplan, se salta.
        for nvtip in ("C", "F"):
            candidates = [{
                "nvfac_nume": "NC001",
                "nvtip_docu": nvtip,
                "nvfac_orde": "OC001",
                "nvfac_totp": 1000,
                "nvfac_stot": 1000,
                "assigned_to": None,
                "has_assigned_users": False,
                "in_queue": True,
            }]
            calls, callbacks = self._callbacks(
                oc_context={"oc_type": "01", "headquarter": "BOG"},
                receipt_bank=[],
                emails=["a@x.com"],
                users=["a@x.com"],
                candidates=candidates,
                resolve_rule_fn=lambda doc: {"rule_code": "no_po"},
                po_exists_fn=lambda oc: True,
            )
            assigned = auto_assign(**callbacks)
            if nvtip == "C":
                self.assertEqual(assigned, [])
                self.assertEqual(calls, [])
            else:
                self.assertEqual(assigned, ["NC001"])


if __name__ == "__main__":
    unittest.main()
