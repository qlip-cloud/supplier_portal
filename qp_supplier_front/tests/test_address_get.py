# -*- coding: utf-8 -*-
import unittest
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

import qp_supplier_front.uses_cases.information.address.get as get_module


class TestNormalize(unittest.TestCase):

    def test_normalize_lowercase_and_accent_insensitive(self):
        self.assertEqual(get_module._normalize("Cajicá"), get_module._normalize("CAJICA"))
        self.assertEqual(get_module._normalize("Cundinamarca"), get_module._normalize("CUNDINAMARCA"))

    def test_normalize_ignores_spaces(self):
        self.assertEqual(get_module._normalize("  Santa Fe de Bogota "), get_module._normalize("santafedebogota"))

    def test_normalize_empty(self):
        self.assertEqual(get_module._normalize(None), "")
        self.assertEqual(get_module._normalize(""), "")


class TestResolveDepartmentMunicipality(unittest.TestCase):

    def setUp(self):
        self.patchers = [
            patch.object(get_module, "_find_state_record"),
            patch.object(get_module, "_find_municipality_record"),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.find_state = get_module._find_state_record
        self.find_municipality = get_module._find_municipality_record

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()

    def test_modern_convention_city_department_state_municipality(self):
        self.find_state.side_effect = lambda value: {
            "25-Cundinamarca": {"name": "25-Cundinamarca", "state_name": "Cundinamarca"}
        }.get(value)
        self.find_municipality.side_effect = lambda value, state_record=None: {
            "126-CAJICA": {"name": "126-CAJICA", "municipality_name": "CAJICA", "state_code": "25-Cundinamarca"}
        }.get(value)

        result = get_module._resolve_department_municipality("25-Cundinamarca", "126-CAJICA")

        self.assertEqual(result["department_code"], "25-Cundinamarca")
        self.assertEqual(result["department_raw"], "25-Cundinamarca")
        self.assertEqual(result["municipality_code"], "126-CAJICA")
        self.assertEqual(result["municipality_raw"], "126-CAJICA")

    def test_legacy_swapped_convention_state_department_city_municipality(self):
        self.find_state.side_effect = lambda value: {
            "CUNDINAMARCA": {"name": "25-Cundinamarca", "state_name": "Cundinamarca"}
        }.get(value)
        self.find_municipality.side_effect = lambda value, state_record=None: {
            "CAJICA": {"name": "126-CAJICA", "municipality_name": "CAJICA", "state_code": "25-Cundinamarca"}
        }.get(value)

        result = get_module._resolve_department_municipality("CAJICA", "CUNDINAMARCA")

        self.assertEqual(result["department_code"], "25-Cundinamarca")
        self.assertEqual(result["department_raw"], "CUNDINAMARCA")
        self.assertEqual(result["municipality_code"], "126-CAJICA")
        self.assertEqual(result["municipality_raw"], "CAJICA")

    def test_unknown_values_keep_raw_fallback(self):
        self.find_state.return_value = None
        self.find_municipality.return_value = None

        result = get_module._resolve_department_municipality("ZZZ", "QQQ")

        self.assertEqual(result["department_code"], "ZZZ")
        self.assertEqual(result["department_raw"], "ZZZ")
        self.assertEqual(result["municipality_code"], "QQQ")
        self.assertEqual(result["municipality_raw"], "QQQ")

    def test_partial_department_found_but_municipality_unknown(self):
        self.find_state.side_effect = lambda value: {
            "CUNDINAMARCA": {"name": "25-Cundinamarca", "state_name": "Cundinamarca"}
        }.get(value)
        self.find_municipality.return_value = None

        result = get_module._resolve_department_municipality("FUNZA", "CUNDINAMARCA")

        self.assertEqual(result["department_code"], "25-Cundinamarca")
        self.assertEqual(result["department_raw"], "CUNDINAMARCA")
        self.assertEqual(result["municipality_code"], "FUNZA")
        self.assertEqual(result["municipality_raw"], "FUNZA")


if __name__ == "__main__":
    unittest.main()
