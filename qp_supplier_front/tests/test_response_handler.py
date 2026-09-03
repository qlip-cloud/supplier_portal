# -*- coding: utf-8 -*-
"""
test_response_handler.py
========================
Pruebas de resources/response.py: el titulo que loguea al Error Log debe ser
string (un dict de data rompia el insert a tabError Log).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_response_handler -v
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.response import handler  # noqa: E402


class TestResponseHandler(unittest.TestCase):

    def setUp(self):
        frappe_mock = sys.modules["frappe"]
        frappe_mock.reset_mock()
        frappe_mock.response = {}

    def test_error_con_data_dict_logea_titulo_string(self):
        handler(400, "fallo", {"classification": "excede"})
        message = sys.modules["frappe"].response["message"]
        self.assertEqual(message["status"], 400)
        self.assertEqual(message["msg"], "fallo")
        self.assertEqual(message["data"], {"classification": "excede"})
        kwargs = sys.modules["frappe"].log_error.call_args[1]
        self.assertIsInstance(kwargs.get("title"), str)
        self.assertIn("excede", kwargs["title"])

    def test_error_sin_data_usa_msg_como_titulo(self):
        handler(422, "error de negocio")
        message = sys.modules["frappe"].response["message"]
        self.assertEqual(message["status"], 422)
        self.assertEqual(message["data"], None)
        kwargs = sys.modules["frappe"].log_error.call_args[1]
        self.assertEqual(kwargs.get("title"), "error de negocio")

    def test_exito_no_loguea_error(self):
        handler(200, "ok", {"a": 1})
        self.assertEqual(sys.modules["frappe"].log_error.call_count, 0)


if __name__ == "__main__":
    unittest.main()