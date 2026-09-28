# -*- coding: utf-8 -*-
"""
test_xml_invoice_reference.py
=============================
Pruebas del parser puro de referencia de factura
(services/xml_invoice_reference.py).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_xml_invoice_reference -v
"""
import os
import unittest

from qp_supplier_front.services.xml_invoice_reference import (
    extract_invoice_document_reference,
)

CDN = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBN = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

CREDIT_NOTE_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<CreditNote xmlns:cac="' + CDN + '" xmlns:cbc="' + CBN + '">'
    '<cac:BillingReference><cac:InvoiceDocumentReference>'
    '<cbc:ID>SETT0501293</cbc:ID></cac:InvoiceDocumentReference>'
    '</cac:BillingReference></CreditNote>'
)

ATTACHED_XML = (
    '<AttachedDocument xmlns:cac="' + CDN + '" xmlns:cbc="' + CBN + '">'
    '<cac:Attachment><cac:ExternalReference><cbc:Description>'
    + CREDIT_NOTE_XML +
    '</cbc:Description></cac:ExternalReference></cac:Attachment>'
    '</AttachedDocument>'
)


class TestExtractInvoiceDocumentReference(unittest.TestCase):

    def test_credit_note_raiz_extrae_referencia(self):
        self.assertEqual(
            extract_invoice_document_reference(CREDIT_NOTE_XML),
            "SETT0501293",
        )

    def test_attached_document_extrae_referencia_del_embebido(self):
        self.assertEqual(
            extract_invoice_document_reference(ATTACHED_XML),
            "SETT0501293",
        )

    def test_sin_referencia_devuelve_none(self):
        xml = (
            '<CreditNote xmlns:cac="' + CDN + '" xmlns:cbc="' + CBN + '">'
            '<cac:BillingReference></cac:BillingReference></CreditNote>'
        )
        self.assertIsNone(extract_invoice_document_reference(xml))

    def test_xml_invalido_devuelve_none(self):
        self.assertIsNone(extract_invoice_document_reference("<not xml"))
        self.assertIsNone(extract_invoice_document_reference(None))
        self.assertIsNone(extract_invoice_document_reference(""))

    def test_referencia_del_archivo_ejemplo(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))),
            "qp_supplier_front",
            "context",
            "referencia.xml",
        )
        if not os.path.exists(path):
            self.skipTest("referencia.xml no disponible")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertEqual(
            extract_invoice_document_reference(content),
            "SETT0501293",
        )


if __name__ == "__main__":
    unittest.main()