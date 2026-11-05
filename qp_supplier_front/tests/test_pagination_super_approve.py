# -*- coding: utf-8 -*-
"""Regresion: la paginacion AJAX debe pasar can_super_approve al template."""

import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe_mock = MagicMock()
_frappe_mock.whitelist.side_effect = lambda *args, **kwargs: (lambda fn: fn)
sys.modules["frappe"] = _frappe_mock

from qp_supplier_front.resources.utils import pagination  # noqa: E402


class TestRenderPaginationSuperApprove(unittest.TestCase):

    def _render(self):
        captured = {}

        def fake_render(template, context):
            captured.update(context)
            return "ok"

        with patch.object(pagination, "frappe") as frappe_mock, \
                patch.object(pagination, "response"), \
                patch.object(
                    pagination, "get_assigned_sync_lines_filters",
                    return_value={}), \
                patch.object(
                    pagination, "get_assigned_sync_line_names",
                    return_value=[]), \
                patch.object(
                    pagination, "get_paginated_filtered",
                    return_value=[]), \
                patch.object(
                    pagination, "can_super_approve_current_user",
                    return_value=True), \
                patch.object(
                    pagination, "is_sede_documenteme",
                    return_value=False), \
                patch.object(
                    pagination, "get_sync_backend",
                    return_value="BC"):
            frappe_mock.get_roles.return_value = []
            frappe_mock.session.user = "ruth.torin@mentum.com.co"
            frappe_mock.render_template.side_effect = fake_render
            pagination.render_pagination(
                0, "documenteme_sales_invoices", "qp_SP_DocumentDetail",
                "", "", "creation", '{"name":"SETT0501145"}',
            )

        return captured

    def test_incluye_can_super_approve_en_el_contexto(self):
        self.assertTrue(self._render().get("can_super_approve"))


if __name__ == "__main__":
    unittest.main()
