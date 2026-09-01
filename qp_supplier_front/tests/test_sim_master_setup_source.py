# -*- coding: utf-8 -*-
"""
test_sim_master_setup_source.py
================================
Adaptador de config de qp_SP_MasterSetup: implementacion de memoria
(MemoryMasterSetupSource) sin tocar frappe, implementacion real
(RealMasterSetupSource) delegando a frappe, y la independencia entre ambos
(la simulacion no lee la config real y viceversa).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_master_setup_source -v
"""
import unittest
from unittest.mock import MagicMock

from qp_supplier_front.infrastructure.adapters.master_setup_source import (
    RealMasterSetupSource,
    resolve_master_setup_source,
)
from qp_supplier_front.simulation import seeds
from qp_supplier_front.simulation.master_setup_source import (
    MemoryMasterSetupSource,
)
from qp_supplier_front.simulation.store import MemoryStore


class TestMemoryMasterSetupSource(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        seeds.seed_scenario(self.store)
        self.source = MemoryMasterSetupSource(self.store)

    def test_lee_valores_sembrados(self):
        self.assertTrue(self.source.auto_approve_enabled())
        self.assertEqual(self.source.auto_reject_rule(), "RULE-NO-PO")

    def test_campo_no_sembrado_devuelve_none(self):
        source = MemoryMasterSetupSource(MemoryStore())
        self.assertFalse(source.auto_approve_enabled())
        self.assertIsNone(source.auto_reject_rule())
        self.assertEqual(source.sede_source_doctype(), "qp_md_headquarter")

    def test_reject_config_con_defaults(self):
        config = self.source.reject_config()
        self.assertEqual(config["max_attempts"], 5)
        self.assertEqual(config["retry_interval"], 60)
        self.assertEqual(config["event_delay"], 60)

    def test_facade_expone_master_setup_de_memoria(self):
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        facade = DataFacade(store=self.store)
        self.assertIsInstance(facade.master_setup, MemoryMasterSetupSource)
        self.assertTrue(facade.master_setup.auto_approve_enabled())

    def test_independencia_no_lee_config_real(self):
        # La simulacion lee del store, aunque frappe real devuelva otra cosa.
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "RULE-REAL"
        self.assertEqual(self.source.auto_reject_rule(), "RULE-NO-PO")
        frappe_mock.db.get_single_value.assert_not_called()


class TestRealMasterSetupSource(unittest.TestCase):

    def test_auto_approve_enabled(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = 1
        source = RealMasterSetupSource(frappe_module=frappe_mock)
        self.assertTrue(source.auto_approve_enabled())
        frappe_mock.db.get_single_value.assert_called_once_with(
            "qp_SP_MasterSetup", "auto_approve")

    def test_auto_reject_rule(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "RULE"
        source = RealMasterSetupSource(frappe_module=frappe_mock)
        self.assertEqual(source.auto_reject_rule(), "RULE")

    def test_reject_config_defaults_cuando_vacio(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = None
        config = RealMasterSetupSource(
            frappe_module=frappe_mock).reject_config()
        self.assertEqual(config, {"max_attempts": 5, "retry_interval": 60,
                                  "event_delay": 60})

    def test_sede_source_con_default(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = None
        source = RealMasterSetupSource(frappe_module=frappe_mock)
        self.assertEqual(source.sede_source_doctype(), "qp_md_headquarter")


class TestResolveMasterSetupSource(unittest.TestCase):

    def test_con_data_usa_el_adaptador_de_memoria(self):
        store = MemoryStore()
        seeds.seed_scenario(store)
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        data = DataFacade(store=store)
        self.assertIsInstance(
            resolve_master_setup_source(data=data),
            MemoryMasterSetupSource)

    def test_sin_data_usa_real(self):
        frappe_mock = MagicMock()
        source = resolve_master_setup_source(
            data=None, frappe_module=frappe_mock)
        self.assertIsInstance(source, RealMasterSetupSource)
        self.assertIs(source._frappe, frappe_mock)


if __name__ == "__main__":
    unittest.main()