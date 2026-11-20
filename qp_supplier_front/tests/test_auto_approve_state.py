# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.services import auto_approve_state as module


class TestAutoApproveState(unittest.TestCase):

    def _cache(self):
        cache = MagicMock()
        values = {}

        def set_value(key, value, **kwargs):
            values[key] = value

        def get_value(key, **kwargs):
            return values.get(key)

        def delete_value(keys):
            for key in keys:
                values.pop(key, None)

        cache.set_value.side_effect = set_value
        cache.get_value.side_effect = get_value
        cache.delete_value.side_effect = delete_value
        return cache

    def test_marca_y_limpia(self):
        cache = self._cache()
        with patch.object(module, "_cache", return_value=cache):
            module.mark_processing(["DOC1"])
            self.assertTrue(module.is_processing("DOC1"))
            self.assertFalse(module.is_processing("DOC2"))
            module.clear_processing(["DOC1"])
            self.assertFalse(module.is_processing("DOC1"))

    def test_lee_sin_cachear_none_local(self):
        """La lectura usa expires=True para no tapar la marca recien escrita."""
        cache = MagicMock()
        cache.get_value.return_value = None
        with patch.object(module, "_cache", return_value=cache):
            module.is_processing("DOC1")
        cache.get_value.assert_called_once_with(
            "documenteme_auto_approve_doc:DOC1", expires=True)

    def test_nombre_vacio(self):
        self.assertFalse(module.is_processing(""))
        self.assertFalse(module.is_processing(None))


if __name__ == "__main__":
    unittest.main()
