# -*- coding: utf-8 -*-
"""
test_auto_reject.py
===================
Pruebas unitarias para uses_cases/documenteme/auto_reject.py.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_reject.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    RULE_NO_PO,
    RULE_NO_PO_NO_RECEIPT,
    RULE_NO_RECEIPT,
    auto_reject,
    collect_rejectable,
    get_reject_motive,
    has_po_match,
    has_receipt_match,
    is_active_rule,
    is_eligible_doc,
    resolve_auto_reject_config,
    should_auto_reject,
)


def _rule(rule_code, enabled=1, motive=None, rule_name=None):
    return {
        "rule_name": rule_name or rule_code,
        "rule_code": rule_code,
        "enabled": enabled,
        "motive": motive,
    }


def _invoice(nvfac_orde="OC111", nvfac_esta="E", nvfac_ueve=None,
             name="DOC1", nvfac_nume="DOC1"):
    return {
        "name": name,
        "nvfac_nume": nvfac_nume,
        "nvfac_orde": nvfac_orde,
        "nvfac_esta": nvfac_esta,
        "nvfac_ueve": nvfac_ueve,
    }


class TestResolveAutoRejectConfig(unittest.TestCase):

    def test_proveedor_activo_gana_al_setup(self):
        supplier = _rule(RULE_NO_PO)
        setup = _rule(RULE_NO_RECEIPT)
        self.assertEqual(
            resolve_auto_reject_config(supplier, setup)["rule_code"],
            RULE_NO_PO,
        )

    def test_sin_proveedor_usa_setup(self):
        self.assertEqual(
            resolve_auto_reject_config(None, _rule(RULE_NO_RECEIPT))["rule_code"],
            RULE_NO_RECEIPT,
        )

    def test_proveedor_vacio_usa_setup(self):
        self.assertEqual(
            resolve_auto_reject_config({}, _rule(RULE_NO_PO))["rule_code"],
            RULE_NO_PO,
        )

    def test_ambos_vacios_retorna_none(self):
        self.assertIsNone(resolve_auto_reject_config(None, None))

    def test_proveedor_deshabilitado_usa_setup(self):
        supplier = _rule(RULE_NO_PO, enabled=0)
        setup = _rule(RULE_NO_RECEIPT)
        self.assertEqual(
            resolve_auto_reject_config(supplier, setup)["rule_code"],
            RULE_NO_RECEIPT,
        )

    def test_ambos_deshabilitados_retorna_none(self):
        supplier = _rule(RULE_NO_PO, enabled=0)
        setup = _rule(RULE_NO_RECEIPT, enabled=0)
        self.assertIsNone(resolve_auto_reject_config(supplier, setup))


class TestIsActiveRule(unittest.TestCase):

    def test_regla_valida_activa(self):
        self.assertTrue(is_active_rule(_rule(RULE_NO_PO)))

    def test_none(self):
        self.assertFalse(is_active_rule(None))

    def test_regla_deshabilitada(self):
        self.assertFalse(is_active_rule(_rule(RULE_NO_PO, enabled=0)))

    def test_codigo_desconocido(self):
        self.assertFalse(is_active_rule(_rule("unknown_code")))


class TestGetRejectMotive(unittest.TestCase):

    def test_usa_motive_del_registro(self):
        rule = _rule(RULE_NO_PO, motive="Motivo custom")
        self.assertEqual(get_reject_motive(rule), "Motivo custom")

    def test_fallback_al_default_por_codigo(self):
        self.assertIn(
            "orden de compra",
            get_reject_motive(_rule(RULE_NO_PO, motive="")),
        )

    def test_default_recibo(self):
        self.assertIn(
            "recibo de compra",
            get_reject_motive(_rule(RULE_NO_RECEIPT, motive="")),
        )


class TestHasPoMatch(unittest.TestCase):

    def test_sin_oc_retorna_false(self):
        self.assertFalse(has_po_match(_invoice(nvfac_orde=""), lambda o: True))

    def test_oc_existente_retorna_true(self):
        self.assertTrue(has_po_match(_invoice(), lambda o: o == "OC111"))

    def test_oc_inexistente_retorna_false(self):
        self.assertFalse(has_po_match(_invoice(), lambda o: False))


class TestHasReceiptMatch(unittest.TestCase):

    def test_sin_oc_retorna_false(self):
        self.assertFalse(has_receipt_match(_invoice(nvfac_orde=""), lambda o: 100))

    def test_con_recibos_retorna_true(self):
        self.assertTrue(has_receipt_match(_invoice(), lambda o: 100))

    def test_sin_recibos_retorna_false(self):
        self.assertFalse(has_receipt_match(_invoice(), lambda o: None))


class TestShouldAutoReject(unittest.TestCase):

    def test_none_retorna_false(self):
        self.assertFalse(should_auto_reject(False, False, None))

    def test_no_po_rechaza_sin_oc(self):
        self.assertTrue(should_auto_reject(False, True, RULE_NO_PO))

    def test_no_po_no_rechaza_con_oc(self):
        self.assertFalse(should_auto_reject(True, False, RULE_NO_PO))

    def test_no_receipt_rechaza_sin_recibo(self):
        self.assertTrue(should_auto_reject(True, False, RULE_NO_RECEIPT))

    def test_no_receipt_no_rechaza_con_recibo(self):
        self.assertFalse(should_auto_reject(True, True, RULE_NO_RECEIPT))

    def test_no_po_no_receipt_rechaza_solo_sin_ambos(self):
        self.assertTrue(should_auto_reject(False, False, RULE_NO_PO_NO_RECEIPT))
        self.assertFalse(should_auto_reject(True, False, RULE_NO_PO_NO_RECEIPT))
        self.assertFalse(should_auto_reject(False, True, RULE_NO_PO_NO_RECEIPT))

    def test_codigo_desconocido_retorna_false(self):
        self.assertFalse(should_auto_reject(False, False, "unknown"))


class TestIsEligibleDoc(unittest.TestCase):

    def test_estado_E_es_elegible(self):
        self.assertTrue(is_eligible_doc(_invoice(nvfac_esta="E")))

    def test_estado_V_no_es_elegible(self):
        self.assertFalse(is_eligible_doc(_invoice(nvfac_esta="V")))

    def test_estado_T_no_es_elegible(self):
        self.assertFalse(is_eligible_doc(_invoice(nvfac_esta="T")))

    def test_estado_A_no_es_elegible(self):
        self.assertFalse(is_eligible_doc(_invoice(nvfac_esta="A")))

    def test_estado_R_no_es_elegible(self):
        self.assertFalse(is_eligible_doc(_invoice(nvfac_esta="R")))

    def test_con_ueve_no_es_elegible(self):
        self.assertFalse(is_eligible_doc(_invoice(nvfac_ueve="031")))


class TestCollectRejectable(unittest.TestCase):

    def _resolve(self, rule):
        return lambda doc: rule

    def test_filtra_solo_regla_no_po(self):
        candidates = [
            _invoice(name="DOC1", nvfac_orde="OC111"),
            _invoice(name="DOC2", nvfac_orde="OC222"),
        ]
        rejectable = collect_rejectable(
            candidates,
            self._resolve(_rule(RULE_NO_PO)),
            lambda o: o == "OC111",
            lambda o: 100,
        )
        self.assertEqual(len(rejectable), 1)
        self.assertEqual(rejectable[0]["doc"]["name"], "DOC2")

    def test_regla_no_receipt(self):
        candidates = [
            _invoice(name="DOC1", nvfac_orde="OC111"),
            _invoice(name="DOC2", nvfac_orde="OC222"),
        ]
        rejectable = collect_rejectable(
            candidates,
            self._resolve(_rule(RULE_NO_RECEIPT)),
            lambda o: True,
            lambda o: 100 if o == "OC111" else None,
        )
        self.assertEqual([r["doc"]["name"] for r in rejectable], ["DOC2"])

    def test_sin_regla_no_rechaza(self):
        rejectable = collect_rejectable(
            [_invoice()],
            lambda doc: None,
            lambda o: False,
            lambda o: None,
        )
        self.assertEqual(rejectable, [])

    def test_regla_deshabilitada_no_aplica(self):
        rejectable = collect_rejectable(
            [_invoice()],
            self._resolve(_rule(RULE_NO_PO, enabled=0)),
            lambda o: False,
            lambda o: None,
        )
        self.assertEqual(rejectable, [])


class TestAutoReject(unittest.TestCase):

    def _run(self, candidates, rule, po_exists_fn, receipt_fn):
        return auto_reject(
            candidates_fn=lambda: candidates,
            resolve_rule_fn=lambda doc: rule,
            po_exists_fn=po_exists_fn,
            receipt_for_po_fn=receipt_fn,
        )

    def test_recolecta_descriptores(self):
        result = self._run(
            [_invoice(name="DOC1")],
            _rule(RULE_NO_PO, rule_name="Sin coincidencia con Orden de Compra"),
            lambda o: False,
            lambda o: None,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["doc"], "DOC1")
        self.assertEqual(result[0]["rule"], "Sin coincidencia con Orden de Compra")
        self.assertEqual(result[0]["motive"], get_reject_motive(_rule(RULE_NO_PO)))

    def test_descarta_candidatos_no_E(self):
        candidates = [
            _invoice(name="DOC1", nvfac_esta="E"),
            _invoice(name="DOC2", nvfac_esta="V"),
            _invoice(name="DOC3", nvfac_esta="A"),
        ]
        result = self._run(
            candidates,
            _rule(RULE_NO_PO),
            lambda o: False,
            lambda o: None,
        )
        self.assertEqual([r["doc"] for r in result], ["DOC1"])

    def test_sin_candidatos_retorna_vacio(self):
        result = self._run([], _rule(RULE_NO_PO), lambda o: False, lambda o: None)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
