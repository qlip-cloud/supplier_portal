# -*- coding: utf-8 -*-
"""
test_documenteme_detail_templates.py
====================================
Render de los templates del detalle de factura (fila y modal) con un doble de
`frappe`. Verifica las dos ramas: inline (pocas OC/recibos) y resumen (muchas),
y que el modal use los partials compartidos.
"""

import os
import unittest

import jinja2

APP_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))


class _Utils(object):
    def formatdate(self, value, fmt=None):
        return "16-07-2026"

    def fmt_money(self, value, currency=None):
        return "$" + str(value)


class _Frappe(object):
    utils = _Utils()


def _env():
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(APP_ROOT),
        autoescape=False,
    )


def _product():
    return {
        "codigo": "SH1", "udm": "UN", "cantidad": 1,
        "valor_unitario": 1000, "valor_total": 1000,
        "precio_difiere": False, "precio_grupo": None,
    }


def _receipt(name, order):
    return {
        "name": name, "etiqueta": name, "oc": order, "fecha": "2026-07-16",
        "monto": 1000, "claimed_by_me": False, "selectable": True,
        "productos": [_product()],
    }


def _row(limited):
    orders = ["OC%03d" % index for index in range(1, 6)]
    return {
        "name": "DOC:1", "nvfac_nume": "FAC-1", "nvpro_ndoc": "9001",
        "nvpro_nomb": "Proveedor", "nvtip_docu": "F",
        "nvfac_fech": None, "nvfac_venc": None, "nvfac_conv": "2",
        "factura_interna": "", "factura_interna_code": "",
        "nvfac_stot": 1000, "nvfac_viva": 190, "nvfac_totp": 1190,
        "nvfac_esta": "V", "auto_approve_processing": False,
        "has_unread_conversation": False, "alert_severity": "ninguno",
        "notification_tooltip": "", "alert_tooltip": "", "non_xml_count": 0,
        "assigned_to_name": None, "qp_ref_invoice": None,
        "hide_unselected_recibos": False,
        "detail_lines": [{
            "nvpro_codi": "SH1", "nvuni_desc": "UN", "nvdet_tcan": 1,
            "nvdet_valo": 1000, "nvdet_vdes": 0, "nvdet_stot": 1000,
            "precio_difiere": False, "precio_grupo": None,
        }],
        "allowance_charges": [],
        "ordenes_compra": orders,
        "ordenes_compra_detalle": [
            {"numero": order, "productos": [] if limited else [_product()]}
            for order in orders
        ],
        "productos_orden_compra": [] if limited else [_product()],
        "recepciones": ["REC1", "REC2", "REC3", "REC4"],
        "recepciones_detalle": [_receipt("REC1", orders[0])],
        "recepciones_detalle_por_oc": [
            {"numero": orders[0], "recibos": [_receipt("REC1", orders[0])]},
        ],
        "orders_total": 5,
        "receipts_total": 12,
        "receipts_free_count": 10,
        "receipts_free_total": 8000,
        "receipts_claimed_count": 2,
        "receipts_claimed_total": 2000,
        "detail_limited": limited,
    }


class TestDetailTemplates(unittest.TestCase):

    def _render_row(self, limited):
        template = _env().get_template(
            "qp_supplier_front/templates/list/documenteme_sales_invoices/"
            "row.html")
        return template.render(
            row=_row(limited),
            frappe=_Frappe(),
            documenteme_backend="BC",
            can_super_approve=True,
            can_reassign=True,
            is_sede_documenteme=False,
        )

    def test_fila_limitada_muestra_resumen_y_no_el_banco(self):
        html = self._render_row(True)
        self.assertIn("detail-summary", html)
        self.assertIn("btn-invoice-detail", html)
        self.assertIn("+2", html)
        self.assertNotIn("receipt-bank", html)
        self.assertNotIn("oc-products-group", html)

    def test_fila_inline_mantiene_banco_y_productos(self):
        html = self._render_row(False)
        self.assertNotIn("detail-summary", html)
        self.assertIn("receipt-bank", html)
        self.assertIn("oc-products-group", html)
        self.assertIn("receipt-select", html)

    def test_modal_body_incluye_las_dos_pestanas(self):
        template = _env().get_template(
            "qp_supplier_front/templates/modal/invoice_detail_body.html")
        html = template.render(frappe=_Frappe(), detail=_row(False),
                               tab="receipts")
        self.assertIn('data-pane="orders"', html)
        self.assertIn('data-pane="receipts"', html)
        self.assertIn("receipt-bank", html)
        self.assertIn("oc-products-group", html)


if __name__ == "__main__":
    unittest.main()
