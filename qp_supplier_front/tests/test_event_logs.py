# -*- coding: utf-8 -*-
"""
test_event_logs.py
==================
Pruebas del nucleo puro del log de notificaciones documenteme
(uses_cases/documenteme/event_logs.py): decision de upsert (log limpio) y
vistas de resumen/timeline. Sin frappe, sin base.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_event_logs -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.event_logs import (
    APPROVAL_SEQUENCE,
    REJECT_SEQUENCE,
    build_notification_tooltip,
    event_is_success,
    notification_summary,
    notification_timeline,
    plan_event_log,
    resolve_sequence,
    row_is_success,
)


def _row(event_code, status, attempt_date, response=None, error_message=""):
    return {
        "event_code": event_code,
        "status": status,
        "attempt_date": attempt_date,
        "response": response,
        "error_message": error_message,
    }


class TestEventIsSuccess(unittest.TestCase):

    def test_status_200_result_0(self):
        self.assertTrue(event_is_success({"Result": 0}, 200))

    def test_status_500(self):
        self.assertFalse(event_is_success({"Result": 0}, 500))

    def test_result_1_es_error(self):
        self.assertFalse(event_is_success({"Result": 1}, 200))

    def test_ya_aplicado_cuenta_como_exito(self):
        response = {
            "Result": 1,
            "Description": "El documento [X] ya cuenta con el/los evento(s) "
                           "[033] y se encuentra(n) en estado exitoso.",
        }
        self.assertTrue(event_is_success(response, 200))


class TestRowIsSuccess(unittest.TestCase):

    def test_fila_persistida_string_json(self):
        import json
        row = {
            "status": "200",
            "response": json.dumps({"Result": 0}),
        }
        self.assertTrue(row_is_success(row))

    def test_fila_persistida_error(self):
        import json
        row = {
            "status": "500",
            "response": json.dumps({"Message": "boom"}),
        }
        self.assertFalse(row_is_success(row))


class TestPlanEventLog(unittest.TestCase):

    def test_sin_filas_anexa(self):
        self.assertEqual(plan_event_log([], True), "append")

    def test_reenvio_exitoso_sobre_exitoso_actualiza(self):
        existing = [_row("030", 200, "2026-09-01 10:00:00", {"Result": 0})]
        self.assertEqual(plan_event_log(existing, True), "update")

    def test_primer_fallo_anexa(self):
        existing = [_row("030", 200, "2026-09-01 10:00:00", {"Result": 0})]
        self.assertEqual(plan_event_log(existing, False), "append")

    def test_fallo_previo_luego_exito_anexa(self):
        existing = [_row("033", 500, "2026-09-01 10:00:00", {"Message": "x"})]
        self.assertEqual(plan_event_log(existing, True), "append")


class TestResolveSequence(unittest.TestCase):

    def test_033_determina_aprobacion(self):
        logs = [_row("033", 200, "2026-09-01 10:00:00", {"Result": 0})]
        self.assertEqual(resolve_sequence("BCC", logs), APPROVAL_SEQUENCE)

    def test_031_determina_rechazo(self):
        logs = [_row("031", 500, "2026-09-01 10:00:00")]
        self.assertEqual(resolve_sequence("PR", logs), REJECT_SEQUENCE)

    def test_sin_eventos_por_estado(self):
        self.assertEqual(resolve_sequence("PA", []), APPROVAL_SEQUENCE)
        self.assertEqual(resolve_sequence("PR", []), REJECT_SEQUENCE)
        self.assertEqual(resolve_sequence("E", []), APPROVAL_SEQUENCE)


class TestNotificationSummary(unittest.TestCase):

    def test_todo_ok(self):
        logs = [
            _row("030", 200, "2026-09-01 10:00:00", {"Result": 0}),
            _row("032", 200, "2026-09-01 10:01:00", {"Result": 0}),
            _row("033", 200, "2026-09-01 10:02:00", {"Result": 0}),
        ]
        summary = notification_summary(logs, APPROVAL_SEQUENCE, "PA")
        self.assertEqual(
            [item["status"] for item in summary], ["ok", "ok", "ok"])

    def test_033_en_proceso(self):
        logs = [
            _row("030", 200, "2026-09-01 10:00:00", {"Result": 0}),
            _row("032", 200, "2026-09-01 10:01:00", {"Result": 0}),
            _row("033", 500, "2026-09-01 10:02:00", {"Message": "boom"}),
        ]
        summary = notification_summary(logs, APPROVAL_SEQUENCE, "PA")
        self.assertEqual(
            [item["status"] for item in summary], ["ok", "ok", "en_proceso"])
        self.assertEqual(summary[-1]["date"], "2026-09-01 10:02:00")

    def test_030_fallido_marca_en_proceso(self):
        logs = [_row("030", 500, "2026-09-01 10:00:00", {"Message": "boom"})]
        summary = notification_summary(logs, APPROVAL_SEQUENCE, "PA")
        self.assertEqual(summary[0]["status"], "en_proceso")
        self.assertEqual(len(summary), 1)

    def test_codigos_no_alcanzados_omiten(self):
        logs = [_row("030", 200, "2026-09-01 10:00:00", {"Result": 0})]
        summary = notification_summary(logs, APPROVAL_SEQUENCE, "PA")
        self.assertEqual([item["event_code"] for item in summary], ["030"])


class TestNotificationTimeline(unittest.TestCase):

    def test_fallas_historicas_y_en_proceso_final(self):
        logs = [
            _row("030", 200, "2026-09-01 10:00:00", {"Result": 0}),
            _row("032", 200, "2026-09-01 10:01:00", {"Result": 0}),
            _row("033", 500, "2026-09-01 10:02:00", {"Message": "a"}),
            _row("033", 500, "2026-09-01 10:05:00", {"Message": "b"}),
        ]
        timeline = notification_timeline(logs, APPROVAL_SEQUENCE, "PA")
        self.assertEqual([item["status"] for item in timeline],
                         ["ok", "ok", "fail", "en_proceso"])

    def test_todo_ok(self):
        logs = [
            _row("030", 200, "2026-09-01 10:00:00", {"Result": 0}),
            _row("032", 200, "2026-09-01 10:01:00", {"Result": 0}),
            _row("031", 200, "2026-09-01 10:02:00", {"Result": 0}),
        ]
        timeline = notification_timeline(logs, REJECT_SEQUENCE, "PR")
        self.assertEqual([item["status"] for item in timeline],
                         ["ok", "ok", "ok"])

    def test_orden_asc_por_fecha(self):
        logs = [
            _row("033", 500, "2026-09-01 10:05:00", {"Message": "later"}),
            _row("033", 500, "2026-09-01 10:02:00", {"Message": "earlier"}),
        ]
        timeline = notification_timeline(logs, APPROVAL_SEQUENCE, "PA")
        self.assertEqual(timeline[0]["date"], "2026-09-01 10:02:00")
        self.assertEqual(timeline[0]["status"], "fail")
        self.assertEqual(timeline[1]["status"], "en_proceso")


class TestBuildNotificationTooltip(unittest.TestCase):

    def test_lineas_con_fecha(self):
        summary = [
            {"event_code": "030", "status": "ok", "date": "2026-09-01 10:00:00"},
            {"event_code": "032", "status": "ok", "date": "2026-09-01 10:01:00"},
            {"event_code": "033", "status": "en_proceso",
             "date": "2026-09-01 10:05:00"},
        ]
        tooltip = build_notification_tooltip(summary)
        self.assertIn("030 Ok", tooltip)
        self.assertIn("032 Ok", tooltip)
        self.assertIn("033 En proceso", tooltip)
        self.assertIn("2026-09-01 10:05", tooltip)

    def test_sin_resumen_none(self):
        self.assertIsNone(build_notification_tooltip([]))


if __name__ == "__main__":
    unittest.main()