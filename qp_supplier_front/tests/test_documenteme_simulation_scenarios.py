# -*- coding: utf-8 -*-
"""
test_documenteme_simulation_scenarios.py
========================================
Escenarios de simulacion en memoria: integran los doubles consolidados de
resources/documenteme/simulation.py con los nucleos puros (uses_cases/) sin
base de datos, cubriendo los criterios de aceptacion clave:

- AC-2 sync entrante servido por fixtures (fases 1-2).
- AC-4 aprobacion simulada: approved con doc_number SIM y estado BCC.
- AC-5 actor de confirmacion: confirmation_id SIMCONF-* (nivel nucleo puro).

Frappe no se importa (los nucleos puros no lo requieren y los doubles son
funciones puras).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_documenteme_simulation_scenarios.py -v
"""
import unittest

from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.uses_cases.documents.sync_by_supplier import sync_by_supplier
from qp_supplier_front.uses_cases.documenteme.approve import approve_documents

SIM_NIT = simulation.SIMULATED_COMPANY_TAX_ID


class TestInboundSyncScenario(unittest.TestCase):

    HEADERS = [
        {"Nvfac_nume": "SIM-FAC-0001", "Nvfac_ueve": "", "Nvpro_ndoc": SIM_NIT},
        {"Nvfac_nume": "SIM-FAC-0002", "Nvfac_ueve": "", "Nvpro_ndoc": SIM_NIT},
    ]

    def test_fase1_entrega_fixtures_y_usa_nit_simulado(self):
        send = simulation.build_inbound_sync_double(headers=self.HEADERS, details={})
        received = {}
        sync_by_supplier(
            supplier_id="COMP-1",
            get_tax_id_fn=lambda _sid: simulation.get_company_tax_id(),
            send_request_fn=send,
            create_log_fn=lambda *a, **kw: "LOG-SIM",
            create_lines_fn=lambda log_name, docs: received.update(log=log_name, docs=docs),
            commit_fn=lambda: None,
        )
        self.assertEqual(len(received["docs"]), 2)
        self.assertEqual(received["docs"][0]["Nvfac_nume"], "SIM-FAC-0001")

    def test_fase1_fail_all_no_crea_lineas(self):
        send = simulation.build_inbound_sync_double(
            headers=self.HEADERS, details={}, fail_all=True
        )
        lines_called = []
        sync_by_supplier(
            supplier_id="COMP-1",
            get_tax_id_fn=lambda _sid: simulation.get_company_tax_id(),
            send_request_fn=send,
            create_log_fn=lambda *a, **kw: "LOG-SIM",
            create_lines_fn=lambda log_name, docs: lines_called.append(True),
            commit_fn=lambda: None,
        )
        self.assertFalse(lines_called)


def _make_doc(name="999999999:FAC-001", nvfac_nume="FAC-001",
              nvfac_esta="V", nvfac_conv="2", nvfac_orde="PO-SIM-0001",
              nvfac_totp=1500000):
    return {
        "name": name,
        "nvfac_nume": nvfac_nume,
        "nvpro_ndoc": SIM_NIT,
        "nvfac_fech": "2026-08-25",
        "nvfac_cufe": "CUFE",
        "nvfac_esta": nvfac_esta,
        "nvfac_ueve": None,
        "nvfac_conv": nvfac_conv,
        "nvfac_orde": nvfac_orde,
        "nvfac_totp": nvfac_totp,
        "nvfac_stot": nvfac_totp,
        "nvfac_viva": 0,
        "nvmon_codi": "COP",
    }


class TestApprovalScenario(unittest.TestCase):

    def _run_approve(self, doc):
        approved = []
        registered = []
        get_docs_fn = lambda doc_names: [doc]
        get_lines_fn = lambda d: ([{"item_code": "IT01", "qty": 1, "rate": 100,
                                    "idx": 0, "receiving_no": "", "order_no": ""}], "")
        persist_invoice_fn = lambda d, doc_number, now: doc_number
        mark_registered_fn = lambda d, doc_number: registered.append(
            (doc_number, "BCC")
        )
        return approve_documents(
            [doc["name"]],
            get_docs_fn=get_docs_fn,
            get_lines_fn=get_lines_fn,
            get_headquarter_fn=lambda _po: "HQ01",
            po_exists_fn=lambda _po: True,
            receipts_total_fn=lambda _po: doc.get("nvfac_totp"),
            send_request_fn=simulation.build_send_double(),
            parse_doc_numbers_fn=lambda response: (response or {}).get("invoices") or [],
            persist_invoice_fn=persist_invoice_fn,
            mark_registered_fn=mark_registered_fn,
            mark_error_fn=lambda d, error: None,
            commit_fn=lambda: None,
            now="2026-08-25 10:00:00",
        ), registered

    def test_aprobacion_simulada_approved_con_doc_sim(self):
        doc = _make_doc()
        result, registered = self._run_approve(doc)
        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["doc_number"], "SIMFAC-001")
        self.assertEqual(result["approved"][0]["nvfac_nume"], "FAC-001")
        self.assertEqual(registered, [("SIMFAC-001", "BCC")])
        self.assertEqual(result["errors"], [])

    def test_aprobacion_contado_simulada(self):
        doc = _make_doc(nvfac_conv="1", nvfac_orde="")
        result, registered = self._run_approve(doc)
        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["doc_number"], "SIMFAC-001")

    def test_fallo_por_factura_deja_error_y_no_registra(self):
        doc = _make_doc(nvfac_nume="FAIL-001")
        registered = []
        get_docs_fn = lambda doc_names: [doc]

        def lines(d):
            return ([{"item_code": "IT01", "qty": 1, "rate": 100, "idx": 0,
                      "receiving_no": "", "order_no": ""}], "")

        persist_invoice_fn = lambda d, doc_number, now: doc_number
        mark_registered_fn = lambda d, doc_number: registered.append(doc_number)

        send = simulation.build_send_double(fail_numbers=["FAIL-001"])
        result = approve_documents(
            [doc["name"]],
            get_docs_fn=get_docs_fn,
            get_lines_fn=lines,
            get_headquarter_fn=lambda _po: "HQ01",
            po_exists_fn=lambda _po: True,
            receipts_total_fn=lambda _po: doc.get("nvfac_totp"),
            send_request_fn=send,
            parse_doc_numbers_fn=lambda response: (response or {}).get("invoices") or [],
            persist_invoice_fn=persist_invoice_fn,
            mark_registered_fn=mark_registered_fn,
            mark_error_fn=lambda d, error: None,
            commit_fn=lambda: None,
            now="2026-08-25 10:00:00",
        )
        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(registered, [])


class TestConfirmationActorScenario(unittest.TestCase):

    def test_confirma_aprobados_con_id_deterministico(self):
        approved = [
            {"name": "999999999:FAC-001", "nvfac_nume": "FAC-001",
             "doc_number": "SIMFAC-001"},
            {"name": "999999999:FAC-002", "nvfac_nume": "FAC-002",
             "doc_number": "SIMFAC-002"},
        ]
        confirmed = []

        def process_confirmation_fn(doc_number, confirmation_id):
            confirmed.append((doc_number, confirmation_id))
            return {"ok": True, "doc": {"name": doc_number}}

        results = simulation.run_simulated_confirmation(
            approved, process_confirmation_fn=process_confirmation_fn
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(confirmed[0], ("SIMFAC-001", "SIMCONF-SIMFAC-001"))
        self.assertEqual(confirmed[1], ("SIMFAC-002", "SIMCONF-SIMFAC-002"))
        self.assertTrue(all(r["ok"] for r in results))

    def test_no_confirma_duplicados_sin_doc_number(self):
        def process_confirmation_fn(doc_number, confirmation_id):
            return {"ok": True}

        results = simulation.run_simulated_confirmation(
            [{"name": "X", "nvfac_nume": "FAC", "doc_number": "SIMFAC-1"},
             {"name": "Y", "nvfac_nume": "FAC2"}],
            process_confirmation_fn=process_confirmation_fn,
        )
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()