# -*- coding: utf-8 -*-
"""
test_auto_assign_receipt_preference.py
======================================
Preferencia de recepcion del renglon de usuarios de la asignacion automatica
(qp_SP_AssignmentConfigUser.receipt_preference):

  - "Ambos": recibe documentos con y sin recepcion (default).
  - "Con Recepcion": solo documentos con recepcion.
  - "Sin Recepcion": solo documentos sin recepcion.

Solo aplica al renglon de USUARIOS; los emails resueltos por roles no se
filtran. Un documento "tiene recepcion" cuando el banco de recepciones de su
OC no esta vacio.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_auto_assign_receipt_preference -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.auto_assign import (
    auto_assign,
    resolve_assignee_emails,
)

OC_TYPE_ROWS = [
    {"oc_type": "01", "is_inventariable": 1},
]


def _row(emails, preferences=None, oc_type="01", headquarter="BOG",
         roles=None):
    return {
        "headquarter": headquarter,
        "oc_type": oc_type,
        "user_emails": list(emails),
        "user_preferences": dict(preferences or {}),
        "user_roles": list(roles or []),
    }


class TestPreferenceAllows(unittest.TestCase):

    def test_sin_has_receipt_no_filtra(self):
        self.assertTrue(resolve_assignee_emails(
            "01", "BOG", OC_TYPE_ROWS,
            [_row(["a@x.com"], {"a@x.com": "Sin Recepcion"})],
            has_receipt=None,
        ) == ["a@x.com"])

    def test_ambos_pasa_con_y_sin_recepcion(self):
        rows = [_row(["a@x.com"], {"a@x.com": "Ambos"})]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=True),
            ["a@x.com"],
        )
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=False),
            ["a@x.com"],
        )

    def test_con_recepcion_solo_con_recepcion(self):
        rows = [_row(["a@x.com"], {"a@x.com": "Con Recepcion"})]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=True),
            ["a@x.com"],
        )
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=False),
            [],
        )

    def test_sin_recepcion_solo_sin_recepcion(self):
        rows = [_row(["a@x.com"], {"a@x.com": "Sin Recepcion"})]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=True),
            [],
        )
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=False),
            ["a@x.com"],
        )

    def test_preferencia_ausente_o_vacia_equivale_a_ambos(self):
        rows = [
            _row(["a@x.com", "b@x.com"], {"b@x.com": ""}),
        ]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=True),
            ["a@x.com", "b@x.com"],
        )
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=False),
            ["a@x.com", "b@x.com"],
        )

    def test_preferencia_desconocida_se_trata_como_ambos(self):
        rows = [_row(["a@x.com"], {"a@x.com": "Otra cosa"})]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=False),
            ["a@x.com"],
        )

    def test_roles_no_se_filtran(self):
        rows = [_row([], {"rol@x.com": "Sin Recepcion"},
                     roles=["Alpla Compras"])]
        emails = resolve_assignee_emails(
            "01", "BOG", OC_TYPE_ROWS, rows,
            roles_to_users_fn=lambda roles: ["rol@x.com"],
            has_receipt=True,
        )
        self.assertEqual(emails, ["rol@x.com"])

    def test_mismo_usuario_en_varias_filas_pasa_si_alguna_lo_permite(self):
        rows = [
            _row(["a@x.com"], {"a@x.com": "Sin Recepcion"}),
            _row(["a@x.com", "b@x.com"],
                 {"a@x.com": "Ambos", "b@x.com": "Sin Recepcion"},
                 oc_type="No aplica"),
        ]
        self.assertEqual(
            resolve_assignee_emails("01", "BOG", OC_TYPE_ROWS, rows,
                                    has_receipt=True),
            ["a@x.com"],
        )

    def test_filtro_aplica_a_catch_all_contado_sin_oc(self):
        rows = [
            _row(["ambos@x.com", "sin@x.com", "con@x.com"],
                 {"ambos@x.com": "Ambos", "sin@x.com": "Sin Recepcion",
                  "con@x.com": "Con Recepcion"},
                 oc_type="", headquarter=""),
        ]
        self.assertEqual(
            resolve_assignee_emails(None, None, OC_TYPE_ROWS, rows,
                                    has_receipt=False),
            ["ambos@x.com", "sin@x.com"],
        )


class TestAutoAssignReceiptPreference(unittest.TestCase):

    def _callbacks(self, candidates, receipt_bank, emails, users,
                   received=None, resolve_rule_fn=None, po_exists_fn=None):
        calls = []
        received = received if received is not None else []

        def candidates_fn():
            return list(candidates)

        def get_oc_context_fn(purchase_order_number):
            return {"oc_type": "01", "headquarter": "BOG"}

        def get_receipt_bank_fn(purchase_order_number):
            return receipt_bank

        def resolve_emails_fn(oc_type, headquarter, has_receipt=None):
            received.append(has_receipt)
            return emails

        def resolve_users_fn(resolved_emails):
            return resolved_emails

        def add_assignees_fn(sync_line_name, assignees):
            calls.append((sync_line_name, list(assignees)))

        return calls, received, {
            "candidates_fn": candidates_fn,
            "get_oc_context_fn": get_oc_context_fn,
            "get_receipt_bank_fn": get_receipt_bank_fn,
            "resolve_emails_fn": resolve_emails_fn,
            "resolve_users_fn": resolve_users_fn,
            "add_assignees_fn": add_assignees_fn,
            "resolve_rule_fn": resolve_rule_fn,
            "po_exists_fn": po_exists_fn,
        }

    def _invoice(self, conv="2", orde="OC001"):
        return {
            "nvfac_nume": "FAC001",
            "nvfac_orde": orde,
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "nvfac_conv": conv,
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        }

    def test_documento_con_recepcion_pasa_has_receipt_true(self):
        calls, received, callbacks = self._callbacks(
            candidates=[self._invoice()],
            receipt_bank=[{"name": "R1", "amount": 400,
                           "date": "2026-01-01", "qp_invoice": None}],
            emails=["con@x.com"],
            users=["con@x.com"],
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(received, [True])
        self.assertEqual(calls, [("FAC001", ["con@x.com"])])

    def test_documento_sin_recepcion_pasa_has_receipt_false(self):
        calls, received, callbacks = self._callbacks(
            candidates=[self._invoice()],
            receipt_bank=[],
            emails=["sin@x.com"],
            users=["sin@x.com"],
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(received, [False])

    def test_contado_sin_oc_catch_all_pasa_has_receipt_false(self):
        calls, received, callbacks = self._callbacks(
            candidates=[self._invoice(conv="1", orde="")],
            receipt_bank=[],
            emails=["sin@x.com"],
            users=["sin@x.com"],
            resolve_rule_fn=lambda invoice: {"rule_code": "no_po"},
            po_exists_fn=lambda po: False,
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, ["FAC001"])
        self.assertEqual(received, [False])

    def test_sin_destinatarios_elegibles_no_asigna(self):
        calls, received, callbacks = self._callbacks(
            candidates=[self._invoice()],
            receipt_bank=[],
            emails=[],
            users=[],
        )

        assigned = auto_assign(**callbacks)

        self.assertEqual(assigned, [])
        self.assertEqual(calls, [])
        self.assertEqual(received, [False])


if __name__ == "__main__":
    unittest.main()
