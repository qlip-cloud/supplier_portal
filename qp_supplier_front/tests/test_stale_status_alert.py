# -*- coding: utf-8 -*-
"""
test_stale_status_alert.py
==========================
Pruebas unitarias para la alerta de estatus no definitivo (>48h) de las
facturas documenteme:

- Nucleo puro: uses_cases/documenteme/stale_status_alert.py
- Infra: resources/documenteme/stale_status_alert.py

Aisladas de la base de datos: frappe se inyecta en sys.modules como mock.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_stale_status_alert.py -v
"""
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

_sys_mods_saved = {}
for _module_name in ("frappe", "frappe.utils", "frappe.model", "frappe.model.document"):
    _sys_mods_saved[_module_name] = sys.modules.get(_module_name)
    sys.modules[_module_name] = MagicMock()

from qp_supplier_front.uses_cases.documenteme.stale_status_alert import (  # noqa: E402
    ANALYSIS_STATES,
    build_alert_message,
    cutoff_datetime,
    is_analysis,
    is_older_than,
    parse_creation,
    should_alert,
)


def _doc(nvfac_esta="E", creation=None, name="DOC1", nvfac_nume="FAC001"):
    return {
        "name": name,
        "nvfac_nume": nvfac_nume,
        "nvfac_esta": nvfac_esta,
        "creation": creation,
    }


class TestPureCore(unittest.TestCase):

    def test_analysis_states_son_e_v_t(self):
        for state in ("E", "V", "T"):
            self.assertTrue(is_analysis(state))

    def test_estados_fuera_de_analisis(self):
        for state in ("A", "R", "BCC", "PA", "PR"):
            self.assertFalse(is_analysis(state))

    def test_parse_creation_acepta_datetime(self):
        value = datetime(2026, 8, 20, 10, 0, 0)
        self.assertEqual(parse_creation(value), value)

    def test_parse_creation_acepta_string_sin_microsegundos(self):
        self.assertEqual(
            parse_creation("2026-08-20 10:00:00"),
            datetime(2026, 8, 20, 10, 0, 0),
        )

    def test_parse_creation_acepta_string_con_microsegundos(self):
        self.assertEqual(
            parse_creation("2026-08-20 10:00:00.123456"),
            datetime(2026, 8, 20, 10, 0, 0, 123456),
        )

    def test_parse_creation_valor_invalido_retorna_none(self):
        for value in (None, "no-es-fecha", 12345):
            self.assertIsNone(parse_creation(value))

    def test_is_older_than_mayor_que_umbral(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        creation = now - timedelta(hours=49)
        self.assertTrue(is_older_than(creation, now, threshold_hours=48))

    def test_is_older_than_igual_que_umbral(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        creation = now - timedelta(hours=48)
        self.assertTrue(is_older_than(creation, now, threshold_hours=48))

    def test_is_older_than_menor_que_umbral(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        creation = now - timedelta(hours=47)
        self.assertFalse(is_older_than(creation, now, threshold_hours=48))

    def test_is_older_than_acepta_string(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        creation = (now - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(is_older_than(creation, now, threshold_hours=48))

    def test_should_alert_estado_V_antiguo(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        doc = _doc(nvfac_esta="V", creation=now - timedelta(hours=50))
        self.assertTrue(should_alert(doc, now))

    def test_should_alert_reciente_no_alerta(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        doc = _doc(nvfac_esta="E", creation=now - timedelta(hours=2))
        self.assertFalse(should_alert(doc, now))

    def test_should_alert_estado_final_no_alerta(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        for state in ("A", "R", "BCC", "PA", "PR"):
            doc = _doc(nvfac_esta=state, creation=now - timedelta(days=10))
            self.assertFalse(should_alert(doc, now))

    def test_should_alert_sin_creation_no_alerta(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        self.assertFalse(should_alert(_doc(creation=None), now))

    def test_build_alert_message_incluye_numero(self):
        message = build_alert_message("FAC001", "DOC1")
        self.assertIn("FAC001", message)
        self.assertIn("48 horas", message)

    def test_build_alert_message_fallback_al_name(self):
        message = build_alert_message(None, "DOC1")
        self.assertIn("DOC1", message)

    def test_cutoff_datetime(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        self.assertEqual(
            cutoff_datetime(now, 48),
            now - timedelta(hours=48),
        )


# ---------------------------------------------------------------------------
# Infraestructura
# ---------------------------------------------------------------------------
sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import stale_status_alert as stale_infra  # noqa: E402

for _module_name, _original in _sys_mods_saved.items():
    if _original is None:
        sys.modules.pop(_module_name, None)
    else:
        sys.modules[_module_name] = _original  # noqa: E402


def _candidate(name="DOC1", nvfac_nume="FAC001", nvfac_esta="E", creation=None):
    return {
        "name": name,
        "nvfac_nume": nvfac_nume,
        "nvfac_esta": nvfac_esta,
        "creation": creation,
    }


class TestGenerateStaleStatusAlerts(unittest.TestCase):

    def _frappe_mock(self, documents=None, open_alert_count=0):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = documents if documents is not None else []
        frappe_mock.db.sql.return_value = [[open_alert_count]]
        return frappe_mock

    def test_inserta_alerta_para_documento_en_analisis_viejo(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        frappe_mock = self._frappe_mock(
            documents=[_candidate(creation=now - timedelta(hours=50))]
        )
        with patch.object(stale_infra, "frappe", frappe_mock), \
                patch.object(stale_infra, "insert_alert") as insert_mock:
            inserted = stale_infra.generate_stale_status_alerts(now=now)

        self.assertEqual(inserted, ["DOC1"])
        insert_mock.assert_called_once()
        call_args = insert_mock.call_args[0]
        self.assertEqual(call_args[0], "DOC1")
        self.assertIn("48 horas", call_args[1])
        frappe_mock.db.commit.assert_called()

    def test_no_inserta_documento_reciente(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        frappe_mock = self._frappe_mock(
            documents=[_candidate(creation=now - timedelta(hours=1))]
        )
        with patch.object(stale_infra, "frappe", frappe_mock), \
                patch.object(stale_infra, "insert_alert") as insert_mock:
            inserted = stale_infra.generate_stale_status_alerts(now=now)

        self.assertEqual(inserted, [])
        insert_mock.assert_not_called()

    def test_no_inserta_documento_con_estado_final(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        frappe_mock = self._frappe_mock(
            documents=[_candidate(nvfac_esta="A", creation=now - timedelta(days=5))]
        )
        with patch.object(stale_infra, "frappe", frappe_mock), \
                patch.object(stale_infra, "insert_alert") as insert_mock:
            inserted = stale_infra.generate_stale_status_alerts(now=now)

        self.assertEqual(inserted, [])
        insert_mock.assert_not_called()

    def test_no_duplica_cuando_ya_existe_alerta_abierta(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        frappe_mock = self._frappe_mock(
            documents=[_candidate(creation=now - timedelta(hours=50))],
            open_alert_count=1,
        )
        with patch.object(stale_infra, "frappe", frappe_mock), \
                patch.object(stale_infra, "insert_alert") as insert_mock:
            inserted = stale_infra.generate_stale_status_alerts(now=now)

        self.assertEqual(inserted, [])
        insert_mock.assert_not_called()

    def test_filtra_candidatos_en_consulta(self):
        now = datetime(2026, 8, 20, 10, 0, 0)
        frappe_mock = self._frappe_mock(documents=[])
        with patch.object(stale_infra, "frappe", frappe_mock), \
                patch.object(stale_infra, "insert_alert"):
            stale_infra.generate_stale_status_alerts(now=now)

        frappe_mock.get_all.assert_called_once()
        call_kwargs = frappe_mock.get_all.call_args[1]
        self.assertEqual(
            call_kwargs["filters"]["nvfac_esta"],
            ["in", list(ANALYSIS_STATES)],
        )
        self.assertIn("nvfac_esta", call_kwargs["fields"])
        self.assertIn("creation", call_kwargs["fields"])


class TestHasOpenAlert(unittest.TestCase):

    def _run(self, frappe_mock, parent_name, message):
        with patch.object(stale_infra, "frappe", frappe_mock):
            return stale_infra._has_open_alert(frappe_mock, parent_name, message)

    def test_sin_parent_no_consulta(self):
        frappe_mock = MagicMock()
        self.assertFalse(self._run(frappe_mock, None, "msg"))
        frappe_mock.db.sql.assert_not_called()

    def test_con_alerta_abierta_retorna_true(self):
        frappe_mock = MagicMock()
        frappe_mock.db.sql.return_value = [[1]]
        self.assertTrue(self._run(frappe_mock, "DOC1", "msg"))
        frappe_mock.db.sql.assert_called_once()

    def test_sin_alerta_retorna_false(self):
        frappe_mock = MagicMock()
        frappe_mock.db.sql.return_value = [[0]]
        self.assertFalse(self._run(frappe_mock, "DOC1", "msg"))


if __name__ == "__main__":
    unittest.main()