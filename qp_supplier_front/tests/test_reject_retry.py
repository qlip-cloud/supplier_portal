# -*- coding: utf-8 -*-
"""
test_reject_retry.py
====================
Pruebas unitarias del nucleo puro de reintento del rechazo
(uses_cases/documenteme/reject_retry.py).

Sin dependencias de Frappe.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_reject_retry.py -v
"""
import json
import unittest

from qp_supplier_front.uses_cases.documenteme.reject_retry import (
    EVENT_ORDER,
    build_retry_events,
    get_reject_resume_index,
    is_already_applied,
    is_sequence_successful,
)


def _ok_log(code):
    return {
        "event_code": code,
        "response": {"Result": 0},
        "status": 200,
    }


def _err_log(code):
    return {
        "event_code": code,
        "response": json.dumps({"Result": 1, "Description": "Error"}),
        "status": 200,
    }


def _doc(qp_motive=None):
    class Doc(object):
        nvpro_ndoc = "900123456"
        nvfac_cont = 1
        nvfac_esta = "E"
    doc = Doc()
    doc.qp_motive = qp_motive
    return doc


class TestIsAlreadyApplied(unittest.TestCase):

    def test_ya_cuenta_estado_exitoso(self):
        resp = {
            "Result": 1,
            "Description": (
                "El documento [SETT0501133] ya cuenta con el/los evento(s) "
                "[032] y se encuentra(n) en estado exitoso."
            ),
        }
        self.assertTrue(is_already_applied(resp))

    def test_ya_cuenta_estado_existoso_variante(self):
        # Redaccion exacta reportada ("existoso", no "exitoso")
        resp = {
            "Result": 1,
            "Description": (
                "El documento [SETT0501134] ya cuenta con el/los evento(s) "
                "[032] y se encuentra(n) en estado existoso."
            ),
        }
        self.assertTrue(is_already_applied(resp))

    def test_ya_fue_emitido(self):
        self.assertTrue(is_already_applied(
            {"Result": 1, "Description": "El evento 030 ya fue emitido."}
        ))

    def test_ya_existe(self):
        self.assertTrue(is_already_applied(
            {"Result": 1, "Message": "El evento 032 ya existe."}
        ))

    def test_error_real_no_es_ya_aplicado(self):
        resp = {"Result": 1, "Description": "Error de conexion con la DIAN"}
        self.assertFalse(is_already_applied(resp))

    def test_string_directo(self):
        self.assertTrue(is_already_applied(
            "El documento [X] ya cuenta con el evento [031] en estado exitoso."
        ))
        self.assertFalse(is_already_applied("Falló el envio"))


class TestGetRejectResumeIndex(unittest.TestCase):

    def test_sin_logs_empieza_desde_030(self):
        self.assertEqual(get_reject_resume_index([]), 0)

    def test_no_hay_errores_empieza_desde_030(self):
        logs = [_ok_log("030"), _ok_log("032"), _ok_log("031")]
        self.assertEqual(get_reject_resume_index(logs), 0)

    def test_error_en_031_reanuda_desde_030(self):
        logs = [_ok_log("030"), _ok_log("032"), _err_log("031")]
        self.assertEqual(get_reject_resume_index(logs), EVENT_ORDER.index("030"))

    def test_error_en_032_reanuda_desde_030(self):
        logs = [_ok_log("030"), _err_log("032")]
        self.assertEqual(get_reject_resume_index(logs), EVENT_ORDER.index("030"))

    def test_error_en_030_reanuda_desde_030(self):
        logs = [_err_log("030")]
        self.assertEqual(get_reject_resume_index(logs), EVENT_ORDER.index("030"))

    def test_toma_el_ultimo_error(self):
        # Secuencia completa una vez y error en un reintento posterior
        logs = [_ok_log("030"), _ok_log("032"), _ok_log("031"),
                _ok_log("032"), _err_log("031")]
        self.assertEqual(get_reject_resume_index(logs), EVENT_ORDER.index("030"))

    def test_ya_aplicado_no_cuenta_como_error(self):
        # 032 responde "ya esta aplicado" (no es error), solo 031 falla real.
        # Ante el fallo real de 031 se reinicia desde 030.
        logs = [_ok_log("030"), _err_log("032"), _err_log("031")]
        logs[1]["response"] = {
            "Result": 1,
            "Description": "El documento [X] ya cuenta con el/los evento(s) [032] y se encuentra(n) en estado exitoso.",
        }
        self.assertEqual(get_reject_resume_index(logs), EVENT_ORDER.index("030"))

    def test_ya_aplicado_en_030_con_031_fallido(self):
        # 030 ya aplicado (no error), 032 ok, 031 falla real -> reinicia desde 030
        logs = [_ok_log("030"), _ok_log("032"), _err_log("031")]
        logs[0]["response"] = {
            "Result": 1,
            "Description": "El evento 030 ya fue emitido.",
        }
        self.assertEqual(get_reject_resume_index(logs), EVENT_ORDER.index("030"))


class TestBuildRetryEvents(unittest.TestCase):

    def test_resume_desde_032_envia_032_y_031(self):
        events = build_retry_events(
            _doc(), {"031": {"nvfac_esta": "R"}}, "890900",
            resume_index=EVENT_ORDER.index("032"),
        )
        codes = [e["event_code"] for e in events]
        self.assertEqual(codes, ["032", "031"])
        # el 031 conserva el estado R
        self.assertEqual(events[-1]["payload"]["Nvfac_esta"], "R")

    def test_resume_desde_030_envia_toda_la_secuencia(self):
        events = build_retry_events(
            _doc(), {"031": {"nvfac_esta": "R"}}, "890900",
            resume_index=0,
        )
        codes = [e["event_code"] for e in events]
        self.assertEqual(codes, ["030", "032", "031"])

    def test_base_state_conserva_nvfac_esta_original(self):
        events = build_retry_events(
            _doc(), {"031": {"nvfac_esta": "R"}}, "890900",
            resume_index=0, base_state="E",
        )
        # 030 y 032 usan el estado base, 031 usa el override R
        self.assertEqual(events[0]["payload"]["Nvfac_esta"], "E")
        self.assertEqual(events[1]["payload"]["Nvfac_esta"], "E")
        self.assertEqual(events[2]["payload"]["Nvfac_esta"], "R")

    def test_payload_envia_el_motivo_del_doc(self):
        events = build_retry_events(
            _doc(qp_motive="Rechazada por falta de orden de compra"),
            {"031": {"nvfac_esta": "R"}}, "890900",
            resume_index=0,
        )
        for event in events:
            self.assertEqual(
                event["payload"]["Nvint_desc"],
                "Rechazada por falta de orden de compra",
            )

    def test_payload_sin_motivo_usa_descripcion_default(self):
        events = build_retry_events(
            _doc(), {"031": {"nvfac_esta": "R"}}, "890900",
            resume_index=0,
        )
        for event in events:
            self.assertEqual(
                event["payload"]["Nvint_desc"],
                "Rechazo por error de factura",
            )


class TestIsSequenceSuccessful(unittest.TestCase):

    def test_031_sin_error_es_exito(self):
        sent = [
            {"event_code": "030", "response": {"Result": 0}, "status": 200},
            {"event_code": "032", "response": {"Result": 0}, "status": 200},
            {"event_code": "031", "response": {"Result": 0}, "status": 200},
        ]
        self.assertTrue(is_sequence_successful(sent))

    def test_031_con_error_no_es_exito(self):
        sent = [
            {"event_code": "030", "response": {"Result": 0}, "status": 200},
            {"event_code": "032", "response": {"Result": 0}, "status": 200},
            {"event_code": "031", "response": {"Result": 1}, "status": 200},
        ]
        self.assertFalse(is_sequence_successful(sent))

    def test_031_ya_aplicado_es_exito(self):
        sent = [
            {"event_code": "030", "response": {"Result": 0}, "status": 200},
            {"event_code": "032", "response": {"Result": 0}, "status": 200},
            {"event_code": "031", "response": {
                "Result": 1,
                "Description": "El documento [X] ya cuenta con el/los evento(s) [031] y se encuentra(n) en estado exitoso.",
            }, "status": 200},
        ]
        self.assertTrue(is_sequence_successful(sent))

    def test_vacio_no_es_exito(self):
        self.assertFalse(is_sequence_successful([]))


if __name__ == "__main__":
    unittest.main()
