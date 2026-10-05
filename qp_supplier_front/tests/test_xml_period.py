# -*- coding: utf-8 -*-
"""
test_xml_period.py
==================
Pruebas del parser puro de periodo (cbc:StartDate/cbc:EndDate) de una nota de
credito (services/xml_period.py).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_xml_period -v
"""
import unittest

from qp_supplier_front.services.xml_period import extract_period_dates

CREDIT_NOTE_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<CreditNote xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:'
    'ubl:schema:xsd:CommonBasicComponents-2">'
    '<cbc:IssueDate>2026-09-20</cbc:IssueDate>'
    '<cac:ValidityPeriod>'
    '<cbc:StartDate>2026-09-01</cbc:StartDate>'
    '<cbc:EndDate>2026-09-30</cbc:EndDate>'
    '</cac:ValidityPeriod>'
    '</CreditNote>'
)

ATTACHED_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<AttachedDocument xmlns:cac="urn:oasis:names:specification:ubl:schema:'
    'xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:'
    'specification:ubl:schema:xsd:CommonBasicComponents-2">'
    '<cac:Attachment><cac:ExternalReference>'
    '<cbc:Description>'
    '<?xml version="1.0" encoding="utf-8"?>'
    '<CreditNote xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:'
    'specification:ubl:schema:xsd:CommonBasicComponents-2">'
    '<cac:ValidityPeriod>'
    '<cbc:StartDate>2026-08-01</cbc:StartDate>'
    '<cbc:EndDate>2026-08-31</cbc:EndDate>'
    '</cac:ValidityPeriod>'
    '</CreditNote>'
    '</cbc:Description></cac:ExternalReference></cac:Attachment>'
    '</AttachedDocument>'
)


class TestExtractPeriodDates(unittest.TestCase):

    def test_credit_note_raiz_extrae_rango(self):
        self.assertEqual(
            extract_period_dates(CREDIT_NOTE_XML),
            ("2026-09-01", "2026-09-30"),
        )

    def test_attached_document_extrae_del_embebido(self):
        self.assertEqual(
            extract_period_dates(ATTACHED_XML),
            ("2026-08-01", "2026-08-31"),
        )

    def test_sin_periodo_devuelve_none(self):
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<CreditNote xmlns:cac="urn:oasis:names:specification:ubl:'
            'schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:'
            'names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
            '<cbc:IssueDate>2026-09-20</cbc:IssueDate>'
            '</CreditNote>'
        )
        self.assertEqual(extract_period_dates(xml), (None, None))

    def test_entrada_invalida_devuelve_none(self):
        self.assertEqual(extract_period_dates(None), (None, None))
        self.assertEqual(extract_period_dates(""), (None, None))
        self.assertEqual(extract_period_dates("<not xml"), (None, None))

    def test_solo_fecha_inicio(self):
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<CreditNote xmlns:cbc="urn:oasis:names:specification:ubl:'
            'schema:xsd:CommonBasicComponents-2">'
            '<cbc:StartDate>2026-09-01</cbc:StartDate>'
            '</CreditNote>'
        )
        start, end = extract_period_dates(xml)
        self.assertEqual(start, "2026-09-01")
        self.assertIsNone(end)


if __name__ == "__main__":
    unittest.main()