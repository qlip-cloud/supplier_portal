# -*- coding: utf-8 -*-
"""
test_super_approval.py
======================
Pruebas del nucleo puro de superaprobacion y del gate dentro de
approve_documents.

Ejecutar con:
python -m pytest qp_supplier_front/tests/test_super_approval.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.approve import approve_documents
from qp_supplier_front.uses_cases.documenteme.super_approval import (
    STATE_SUPER_APPROVAL,
    classify,
    difference,
    eligible_supervisors,
    is_super_approver,
    normalize_rows,
    requires_super_approval,
    trigger_limits,
)


def _row(user="super1", **overrides):
    data = {
        "user": user,
        "enabled": 1,
        "threshold_amount": 0,
        "limit_amount": 0,
        "threshold_percentage": 0,
        "limit_percentage": 0,
    }
    data.update(overrides)
    return data


class TestNormalizeRows(unittest.TestCase):

    def test_descarta_deshabilitados_y_sin_usuario(self):
        rows = normalize_rows([
            _row("u1", enabled=0),
            _row("", threshold_percentage=10),
            _row("u2", threshold_percentage=10),
        ])
        self.assertEqual([row["user"] for row in rows], ["u2"])

    def test_convierte_a_float_y_clampea_negativos(self):
        rows = normalize_rows([
            _row("u1", threshold_amount="100.5", limit_amount="-5"),
        ])
        self.assertEqual(rows[0]["threshold_amount"], 100.5)
        self.assertEqual(rows[0]["limit_amount"], 0.0)


class TestDifference(unittest.TestCase):

    def test_diferencia_absoluta_y_porcentaje(self):
        amount, percentage = difference(5000, [{"name": "R1", "amount": 4400}])
        self.assertAlmostEqual(amount, 600.0)
        self.assertAlmostEqual(percentage, 12.0)

    def test_suma_solo_recepciones_seleccionadas(self):
        receipts = [
            {"name": "R1", "amount": 1000},
            {"name": "R2", "amount": 2000},
        ]
        amount, percentage = difference(5000, receipts, selected_names=["R1"])
        self.assertAlmostEqual(amount, 4000.0)
        self.assertAlmostEqual(percentage, 80.0)

    def test_porcentaje_cero_cuando_factura_es_cero(self):
        amount, percentage = difference(0, [{"name": "R1", "amount": 100}])
        self.assertAlmostEqual(amount, 100.0)
        self.assertEqual(percentage, 0.0)


class TestTriggerAndEligibility(unittest.TestCase):

    def test_umbral_es_el_menor_configurado(self):
        rows = normalize_rows([
            _row("u1", threshold_amount=1000),
            _row("u2", threshold_amount=500, threshold_percentage=15),
        ])
        self.assertEqual(trigger_limits(rows), (500, 15))

    def test_sin_umbrales_no_requiere_autorizacion(self):
        rows = normalize_rows([_row("u1")])
        self.assertFalse(requires_super_approval(rows, 9999, 99))

    def test_requiere_por_monto_o_porcentaje(self):
        rows = normalize_rows([_row("u1", threshold_percentage=10)])
        self.assertFalse(requires_super_approval(rows, 10, 9.99))
        self.assertTrue(requires_super_approval(rows, 10, 10.0))

    def test_elegibilidad_por_criterio_independiente(self):
        rows = normalize_rows([
            _row(
                "u1",
                threshold_amount=200,
                limit_amount=1000,
                threshold_percentage=10,
                limit_percentage=11,
            ),
        ])
        self.assertEqual(eligible_supervisors(rows, 600, 12), ["u1"])
        self.assertEqual(eligible_supervisors(rows, 1500, 30), [])

    def test_limite_cero_es_sin_limite(self):
        rows = normalize_rows([
            _row("u1", threshold_amount=100, limit_amount=0),
        ])
        self.assertEqual(eligible_supervisors(rows, 999999, 0), ["u1"])

    def test_es_superaprobador_configurado(self):
        rows = normalize_rows([_row("u1", threshold_percentage=10)])
        self.assertTrue(is_super_approver(rows, "u1"))
        self.assertFalse(is_super_approver(rows, "otro"))


class TestClassify(unittest.TestCase):

    def test_autorizado(self):
        rows = normalize_rows([_row("u1", threshold_percentage=10)])
        info = classify(
            rows, 5000, [{"name": "R1", "amount": 4400}], user="u1"
        )
        self.assertTrue(info["requires_super_approval"])
        self.assertTrue(info["authorized"])
        self.assertFalse(info["blocked"])

    def test_pendiente_para_usuario_normal(self):
        rows = normalize_rows([_row("u1", threshold_percentage=10)])
        info = classify(
            rows, 5000, [{"name": "R1", "amount": 4400}], user="normal"
        )
        self.assertTrue(info["requires_super_approval"])
        self.assertFalse(info["authorized"])
        self.assertEqual(info["supervisors"], ["u1"])
        self.assertFalse(info["blocked"])

    def test_bloqueado_cuando_nadie_cubre(self):
        rows = normalize_rows([
            _row("u1", threshold_amount=100, limit_amount=200),
        ])
        info = classify(
            rows, 5000, [{"name": "R1", "amount": 4400}], user="normal"
        )
        self.assertTrue(info["requires_super_approval"])
        self.assertEqual(info["supervisors"], [])
        self.assertTrue(info["blocked"])


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "FAC001",
        "nvfac_orde": "PO1",
        "nvtip_docu": "F",
        "nvfac_conv": "2",
        "nvfac_esta": "V",
        "nvfac_stot": 5000,
        "document_sync_line": "FAC001",
    }
    data.update(overrides)
    return data


class TestApproveGate(unittest.TestCase):

    NOW = "2026-10-27 10:00:00"

    def _run(self, docs, rows, current_user=None, state="V"):
        calls = {"sent": [], "pending": [], "marked": []}

        def get_docs_fn(doc_names):
            return [dict(doc) for doc in docs if doc["name"] in doc_names]

        def get_lines_fn(doc):
            return [{
                "name": "L1",
                "item_code": "ITEM1",
                "qty": 1,
                "rate": 5000.0,
                "idx": 1,
                "receiving_no": "R1",
                "order_no": "PO1",
            }], ""

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append(payload)
            return {"Result": 0, "invoices": [
                {"doc_number": "BC1", "error": ""} for _ in payload
            ]}, 200

        def mark_pending_super_fn(doc, info, requested_by, now):
            calls["pending"].append({
                "name": doc.get("name"),
                "user": requested_by,
                "supervisors": info.get("supervisors"),
            })

        def mark_error_fn(doc, error):
            calls["marked"].append((doc.get("name"), error))

        result = approve_documents(
            ["DOC1"],
            get_docs_fn=get_docs_fn,
            get_lines_fn=get_lines_fn,
            get_headquarter_fn=lambda po: "HQ",
            po_exists_fn=lambda po: True,
            receipt_bank_fn=lambda po: [
                {"name": "R1", "amount": 4400, "date": "", "qp_invoice": None}
            ],
            selected_receipts={"DOC1": ["R1"]},
            send_request_fn=send_request_fn,
            parse_doc_numbers_fn=lambda response: [
                {"doc_number": "BC1", "error": ""}
            ],
            persist_invoice_fn=lambda doc, doc_number, now: None,
            mark_registered_fn=lambda doc, doc_number: None,
            mark_error_fn=mark_error_fn,
            mark_pending_super_fn=mark_pending_super_fn,
            commit_fn=lambda: None,
            now=self.NOW,
            super_approvers_fn=lambda: rows,
            current_user=current_user,
        )
        return result, calls

    def test_usuario_normal_queda_pendiente_sin_enviar(self):
        rows = [_row("super1", threshold_percentage=10)]
        result, calls = self._run([_doc()], rows, current_user="normal")

        self.assertEqual(result["approved"], [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(calls["sent"], [])
        self.assertEqual(calls["pending"][0]["name"], "DOC1")
        self.assertEqual(calls["pending"][0]["supervisors"], ["super1"])

    def test_superaprobador_elegible_aprueba(self):
        rows = [_row("super1", threshold_percentage=10)]
        result, calls = self._run([_doc()], rows, current_user="super1")

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(calls["sent"]), 1)
        self.assertEqual(calls["pending"], [])

    def test_sin_config_no_aplica_el_gate(self):
        result, calls = self._run([_doc()], [], current_user="normal")

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(calls["sent"]), 1)
        self.assertEqual(calls["pending"], [])

    def test_bloqueo_duro_cuando_nadie_cubre(self):
        rows = [_row("super1", threshold_amount=100, limit_amount=200)]
        result, calls = self._run([_doc()], rows, current_user="normal")

        self.assertEqual(result["approved"], [])
        self.assertEqual(calls["sent"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Ningun superaprobador", result["errors"][0]["error"])

    def test_super_configurado_que_excede_su_limite_no_aprueba(self):
        rows = [_row("super1", threshold_amount=100, limit_amount=200)]
        result, calls = self._run([_doc()], rows, current_user="super1")

        self.assertEqual(result["approved"], [])
        self.assertEqual(calls["sent"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("excede el limite", result["errors"][0]["error"])

    def test_super_aprueba_factura_ya_en_psa(self):
        rows = [_row("super1", threshold_percentage=10)]
        result, calls = self._run(
            [_doc(nvfac_esta=STATE_SUPER_APPROVAL)],
            rows,
            current_user="super1",
        )

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(calls["sent"]), 1)


if __name__ == "__main__":
    unittest.main()
