# -*- coding: utf-8 -*-
"""
test_sync_lock.py
==================
Pruebas unitarias para services/sync_lock.py (mutex de sincronizacion).
Usa un fake cache para no depender de Redis/Frappe.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_sync_lock -v
"""
import unittest
from unittest import mock

import qp_supplier_front.services.sync_lock as lock_mod


class FakeCache:
    def __init__(self):
        self.data = {}

    def make_key(self, key):
        return key

    def set(self, key, value, nx=True, ex=None):
        if key in self.data:
            return None
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)

    def exists(self, key):
        return key in self.data


class TestSyncLock(unittest.TestCase):

    def setUp(self):
        self.cache = FakeCache()
        self.original = lock_mod.frappe_cache
        lock_mod.frappe_cache = lambda: self.cache

    def tearDown(self):
        lock_mod.frappe_cache = self.original

    def test_acquire_first_returns_true(self):
        self.assertTrue(lock_mod.acquire("orders"))

    def test_acquire_second_returns_false(self):
        lock_mod.acquire("orders")
        self.assertFalse(lock_mod.acquire("orders"))

    def test_release_allows_acquire_again(self):
        lock_mod.acquire("orders")
        lock_mod.release("orders")
        self.assertTrue(lock_mod.acquire("orders"))

    def test_is_locked(self):
        self.assertFalse(lock_mod.is_locked("orders"))
        lock_mod.acquire("orders")
        self.assertTrue(lock_mod.is_locked("orders"))

    def test_domains_are_independent(self):
        lock_mod.acquire("orders")
        self.assertTrue(lock_mod.acquire("receipts"))

    def test_acquire_fail_open_when_redis_errors(self):
        def boom():
            raise ConnectionError("no redis")

        lock_mod.frappe_cache = boom
        self.assertTrue(lock_mod.acquire("orders"))
        self.assertFalse(lock_mod.is_locked("orders"))

    def test_wait_for_acquires_when_lock_is_free(self):
        lock_mod.acquire("orders")
        lock_mod.release("orders")
        with mock.patch("time.sleep", return_value=None):
            self.assertTrue(lock_mod.wait_for("orders", timeout=5))

    def test_wait_for_times_out_when_lock_held(self):
        lock_mod.acquire("orders")
        with mock.patch("time.sleep", return_value=None):
            self.assertFalse(lock_mod.wait_for("orders", timeout=5))


if __name__ == "__main__":
    unittest.main()
