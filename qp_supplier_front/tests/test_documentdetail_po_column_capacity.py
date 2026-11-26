# -*- coding: utf-8 -*-
"""
test_documentdetail_po_column_capacity.py
=========================================
Guarda de capacidad de las columnas que guardan las OC de una factura
documenteme, separadas por coma.

`qp_SP_DocumentDetail.qp_manual_purchase_order` / `nvfac_orde` y
`qp_SP_DocumentSyncLine.nvfac_orde` eran `Data` (varchar(140)). Con la
asignacion manual de varias OC fallaba
`(1406, "Data too long for column 'qp_manual_purchase_order'")`; los campos se
cambiaron a `Small Text` (MariaDB `text`, 65,535 bytes).

Ejecutar con:
python -m unittest qp_supplier_front.tests.test_documentdetail_po_column_capacity -v
"""
import json
import os
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DOCTYPES = {
    "qp_SP_DocumentDetail": (
        "qp_sp_documentdetail", "qp_sp_documentdetail.json",
        ("nvfac_orde", "qp_manual_purchase_order"),
    ),
    "qp_SP_DocumentSyncLine": (
        "qp_sp_documentsyncline", "qp_sp_documentsyncline.json",
        ("nvfac_orde",),
    ),
}


class TestMultiOcColumnCapacity(unittest.TestCase):

    def _fields(self, folder, filename):
        path = os.path.join(
            _APP_ROOT, "qp_supplier_front", "doctype", folder, filename)
        with open(path) as fh:
            data = json.load(fh)
        return {field["fieldname"]: field for field in data["fields"]}

    def test_multi_oc_fields_are_small_text(self):
        for doctype, (folder, filename, fieldnames) in _DOCTYPES.items():
            fields = self._fields(folder, filename)
            for fieldname in fieldnames:
                with self.subTest(doctype=doctype, field=fieldname):
                    self.assertEqual(
                        fields[fieldname]["fieldtype"], "Small Text")
                    self.assertNotIn("length", fields[fieldname])
