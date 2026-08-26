# -*- coding: utf-8 -*-
"""
test_characterization_approve_payload.py
========================================
Suite de caracterizacion (BASELINE) para uses_cases/documenteme/approve.py.

Fija el comportamiento ACTUAL de `_build_invoice` / `build_payload` /
`approve_documents` mediante golden values del dict completo tal como se
genera HOY, incluyendo la key "Almacen" (resuelta por el callback
`get_headquarter_fn` a partir de la Purchase Order vinculada).

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con:
    python -m pytest qp_supplier_front/tests/characterization/ -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.approve import (
    approve_documents,
    build_payload,
)


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "FAC001",
        "nvpro_ndoc": "050633410",
        "nvfac_fech": "2026-07-09 10:00:00",
        "nvfac_cufe": "",
        "nvtip_docu": "F",
        "nvfac_fpag": "",
        "nvfac_orde": "45238",
        "nvfac_rece": "R108349",
        "nvfac_totp": 50000,
        "nvfac_esta": "V",
        "nvmon_codi": "COP",
        "nvfac_stot": 50000,
        "nvfac_viva": 0,
    }
    data.update(overrides)
    return data


def _line(**overrides):
    data = {
        "name": "LINE1",
        "item_code": "M000455",
        "qty": 10,
        "rate": 5000.0,
        "idx": 1,
        "receiving_no": "R108349",
        "order_no": "45238",
    }
    data.update(overrides)
    return data


# Orden REAL de insercion de claves en `_build_invoice` hoy.
INVOICE_KEY_ORDER = [
    "invoiceDate",
    "postingDate",
    "vendorNumber",
    "puntofacturacion",
    "NoFacturaProveedor",
    "Cufe",
    "Almacen",
    "tipoFacturaDoc",
    "formaPago",
    "dimensionSetLines",
    "vendorInvoiceLine",
]


def _golden_invoice(no_factura_proveedor, cufe, almacen="HQ01"):
    """Golden dict completo de una factura con una unica linea de recepcion.

    Refleja el comportamiento actual de `_build_invoice` (con "Almacen").
    """
    return {
        "invoiceDate": "2026-07-09",
        "postingDate": "2026-07-09",
        "vendorNumber": "050633410",
        "puntofacturacion": "",
        "NoFacturaProveedor": no_factura_proveedor,
        "Cufe": cufe,
        "Almacen": almacen,
        "tipoFacturaDoc": "Estándar",
        "formaPago": "",
        "dimensionSetLines": [
            {"code": "TERCERO", "valueCode": "050633410"}
        ],
        "vendorInvoiceLine": [
            {
                "NoProducto": "M000455",
                "cantidad": 10,
                "Precio": 5000.0,
                "NoLineaRecepcion": "10000",
                "NoRecepcion": "R108349",
                "NoPedido": "45238",
            }
        ],
    }


class TestBuildPayloadGolden(unittest.TestCase):

    def _get_lines(self, purchase_order):
        return [_line()]

    def _get_headquarter(self, purchase_order):
        return "HQ01"

    def test_payload_un_doc_golden_exacto(self):
        payload = build_payload([_doc()], self._get_lines, self._get_headquarter)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0], _golden_invoice("FAC001", ""))
        self.assertIn("Almacen", payload[0])
        self.assertEqual(payload[0]["Almacen"], "HQ01")

    def test_orden_de_keys_exacto(self):
        payload = build_payload([_doc()], self._get_lines, self._get_headquarter)
        factura = payload[0]
        self.assertEqual(list(factura.keys()), INVOICE_KEY_ORDER)
        self.assertEqual(
            list(factura.keys()).index("Almacen"),
            list(factura.keys()).index("Cufe") + 1,
        )

    def test_cufe_presente_golden(self):
        payload = build_payload(
            [_doc(nvfac_cufe="CUFE123")], self._get_lines, self._get_headquarter
        )
        self.assertEqual(payload[0], _golden_invoice("FAC001", "CUFE123"))
        self.assertIn("Almacen", payload[0])
        self.assertEqual(payload[0]["Almacen"], "HQ01")

    def test_puntofacturacion_sin_headquarter_equivalente(self):
        """`puntofacturacion` es fijo ""; el headquarter viaja en "Almacen"."""
        payload = build_payload([_doc()], self._get_lines, self._get_headquarter)
        factura = payload[0]
        self.assertEqual(factura["puntofacturacion"], "")
        self.assertEqual(factura["Almacen"], "HQ01")

    def test_almacen_vacio_golden(self):
        payload = build_payload([_doc()], self._get_lines, lambda po: "")
        self.assertEqual(payload[0]["Almacen"], "")
        self.assertEqual(payload[0], _golden_invoice("FAC001", "", almacen=""))


class TestApproveDocumentsGolden(unittest.TestCase):

    NOW = "2026-08-12 10:00:00"

    def _callbacks(self, docs, response_obj, status, invoice_results=None,
                   send_raises=None):
        calls = {
            "sent": [],
            "persisted": [],
            "marked": [],
            "marked_error": [],
            "commits": 0,
        }

        def get_docs_fn(doc_names):
            return [d for d in docs if d.get("name") in doc_names]

        def get_lines_fn(purchase_order):
            return [_line()]

        def get_headquarter_fn(purchase_order):
            return "HQ01"

        def po_exists_fn(purchase_order):
            return bool(purchase_order)

        def receipts_total_fn(purchase_order):
            return 50000

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
            if send_raises:
                raise send_raises
            return response_obj, status

        def parse_doc_numbers_fn(resp):
            if invoice_results is None:
                return []
            return invoice_results

        def persist_invoice_fn(doc, doc_number, now):
            calls["persisted"].append((doc.get("nvfac_nume"), doc_number))

        def mark_registered_fn(doc, doc_number):
            calls["marked"].append(doc.get("nvfac_nume"))

        def mark_error_fn(doc, error):
            calls["marked_error"].append((doc.get("nvfac_nume"), error))

        def commit_fn():
            calls["commits"] += 1

        return calls, {
            "get_docs_fn": get_docs_fn,
            "get_lines_fn": get_lines_fn,
            "get_headquarter_fn": get_headquarter_fn,
            "po_exists_fn": po_exists_fn,
            "receipts_total_fn": receipts_total_fn,
            "send_request_fn": send_request_fn,
            "parse_doc_numbers_fn": parse_doc_numbers_fn,
            "persist_invoice_fn": persist_invoice_fn,
            "mark_registered_fn": mark_registered_fn,
            "mark_error_fn": mark_error_fn,
            "commit_fn": commit_fn,
        }

    def test_flujo_completo_exitoso_golden(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001"),
            _doc(name="DOC2", nvfac_nume="FAC002"),
        ]
        results = [
            {"doc_number": "BC1001", "error": ""},
            {"doc_number": "BC1002", "error": ""},
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 0, "invoices": results}, 200,
            invoice_results=results,
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(result, {
            "approved": [
                {
                    "name": "DOC1",
                    "nvfac_nume": "FAC001",
                    "doc_number": "BC1001",
                },
                {
                    "name": "DOC2",
                    "nvfac_nume": "FAC002",
                    "doc_number": "BC1002",
                },
            ],
            "errors": [],
        })

        endpoint_code, payload = calls["sent"][0]
        self.assertEqual(endpoint_code, "create_purchase_order")
        self.assertEqual(payload, [
            _golden_invoice("FAC001", ""),
            _golden_invoice("FAC002", ""),
        ])
        self.assertIn("Almacen", payload[0])
        self.assertIn("Almacen", payload[1])
        self.assertEqual(payload[0]["Almacen"], "HQ01")
        self.assertEqual(payload[1]["Almacen"], "HQ01")

        self.assertEqual(calls["persisted"], [
            ("FAC001", "BC1001"),
            ("FAC002", "BC1002"),
        ])
        self.assertEqual(calls["marked"], ["FAC001", "FAC002"])
        self.assertEqual(calls["marked_error"], [])
        self.assertEqual(calls["commits"], 1)

    def test_docs_invalidos_no_envian_nada_golden(self):
        docs = [_doc(name="DOC1", nvfac_nume="FAC001", nvfac_esta="A")]
        calls, kwargs = self._callbacks(docs, {"Result": 0}, 200)
        result = approve_documents(["DOC1"], now=self.NOW, **kwargs)

        self.assertEqual(result, {
            "approved": [],
            "errors": [
                {
                    "nvfac_nume": "FAC001",
                    "error": "La factura está en un estado definitivo",
                },
            ],
        })
        self.assertEqual(calls["sent"], [])
        self.assertEqual(calls["persisted"], [])
        self.assertEqual(calls["marked"], [])
        self.assertEqual(calls["marked_error"], [])
        self.assertEqual(calls["commits"], 0)

    def test_error_de_bc_marca_todo_en_error_golden(self):
        docs = [
            _doc(name="DOC1", nvfac_nume="FAC001"),
            _doc(name="DOC2", nvfac_nume="FAC002"),
        ]
        calls, kwargs = self._callbacks(
            docs, {"Result": 1, "Description": "BC caido"}, 200,
        )
        result = approve_documents(["DOC1", "DOC2"], now=self.NOW, **kwargs)

        self.assertEqual(result, {
            "approved": [],
            "errors": [
                {"nvfac_nume": "FAC001", "error": "BC caido"},
                {"nvfac_nume": "FAC002", "error": "BC caido"},
            ],
        })
        self.assertEqual(calls["persisted"], [])
        self.assertEqual(calls["marked"], [])
        self.assertEqual(calls["marked_error"], [
            ("FAC001", "BC caido"),
            ("FAC002", "BC caido"),
        ])
        self.assertEqual(calls["commits"], 0)


if __name__ == "__main__":
    unittest.main()
