# -*- coding: utf-8 -*-
"""
test_timeline_origin.py
=======================
Pruebas del origen del historial (manual vs automatico) y del cambio de
usuario a Administrator en jobs de fondo.

El cambio de usuario debe ser SOLO thread-local del worker y nunca tocar una
peticion web viva (ahi se mantiene el usuario actual y el historial igual se
marca automatico por `timeline_origin`).

Solo mocks: no requiere Frappe ni base.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_timeline_origin.py -v
"""
import sys
import types
import unittest
from unittest.mock import patch

from qp_supplier_front.uses_cases.documenteme import timeline_origin


class _FakeFrappe(object):
    def __init__(self, in_request=False):
        self.local = types.SimpleNamespace(
            request=object() if in_request else None)
        self.session = types.SimpleNamespace(user="ruth@example.com")
        self.calls = []

    def set_user(self, user):
        self.calls.append(user)
        self.session.user = user


class TestSystemUser(unittest.TestCase):

    def test_worker_switches_to_administrator_and_restores(self):
        fake = _FakeFrappe(in_request=False)
        with patch.dict(sys.modules, {"frappe": fake}):
            with timeline_origin.system_user():
                self.assertEqual(fake.session.user, "Administrator")
        self.assertEqual(fake.session.user, "ruth@example.com")
        self.assertEqual(
            fake.calls, ["Administrator", "ruth@example.com"])

    def test_web_request_does_not_switch_user(self):
        fake = _FakeFrappe(in_request=True)
        with patch.dict(sys.modules, {"frappe": fake}):
            with timeline_origin.system_user():
                self.assertEqual(fake.session.user, "ruth@example.com")
        self.assertEqual(fake.calls, [])
        self.assertEqual(fake.session.user, "ruth@example.com")

    def test_system_job_decorator(self):
        fake = _FakeFrappe(in_request=False)

        @timeline_origin.system_job
        def job():
            return fake.session.user

        with patch.dict(sys.modules, {"frappe": fake}):
            self.assertEqual(job(), "Administrator")
        self.assertEqual(fake.session.user, "ruth@example.com")

    def test_system_job_no_op_en_peticion_web(self):
        fake = _FakeFrappe(in_request=True)

        @timeline_origin.system_job
        def job():
            return fake.session.user

        with patch.dict(sys.modules, {"frappe": fake}):
            self.assertEqual(job(), "ruth@example.com")
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
