# -*- coding: utf-8 -*-
import unittest
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

import qp_supplier_front.uses_cases.supplier.sync_all as sync_all
from qp_supplier_front.uses_cases.supplier.sync_all import build_records

class TestSupplierSync(unittest.TestCase):

    def setUp(self):
        self.patchers = [
            patch.object(sync_all, '_resolve_state_code', side_effect=lambda s: s),
            patch.object(sync_all, '_resolve_municipality_code', side_effect=lambda c, s: c),
        ]
        for p in self.patchers:
            p.start()

        # Datos de prueba para simular la respuesta de la API
        self.suppliers_response = [
            {
                "vendorId": "1001",
                "nit": "1001",
                "name": "PROVEEDOR NUEVO",
                "phone": "31155512340000",
                "mail": "nuevo@example.com",
                "address": [
                    {
                        "country": "COLOMBIA",
                        "state": "BOGOTA",
                        "city": "BOGOTA",
                        "codCity": None,
                        "address": "Calle Falsa 123"
                    }
                ],
                "eftInformation": None
            },
            {
                "vendorId": "1002",
                "nit": "1002",
                "name": "PROVEEDOR EXISTENTE COMPLETO",
                "phone": "32055556780000",
                "mail": "existente_completo@example.com",
                "address": [
                    {
                        "country": "COLOMBIA",
                        "state": "BOGOTA",
                        "city": "BOGOTA",
                        "codCity": None,
                        "address": "Direccion Existente 456"
                    }
                ],
                "eftInformation": None
            },
            {
                "vendorId": "1003",
                "nit": "1003",
                "name": "PROVEEDOR EXISTENTE SIN NADA",
                "phone": "",
                "mail": "existente_sin_nada@example.com",
                "address": [
                    {
                        "country": "COLOMBIA",
                        "state": "BOGOTA",
                        "city": "BOGOTA",
                        "codCity": None,
                        "address": "Calle Nueva 789"
                    }
                ],
                "eftInformation": None
            },
            {
                "vendorId": "1004",
                "nit": "1004",
                "name": "PROVEEDOR EXISTENTE SOLO TELEFONO",
                "phone": "60123456789000",
                "mail": "",
                "address": [
                    {
                        "country": "COLOMBIA",
                        "state": "BOGOTA",
                        "city": "BOGOTA",
                        "codCity": None,
                        "address": "Calle Telefono 101"
                    }
                ],
                "eftInformation": None
            }
        ]

        # Simular base de datos
        self.existing_suppliers = {
            "1002": "PROV-1002",
            "1003": "PROV-1003",
            "1004": "PROV-1004"
        }
        self.eft_by_vendor = {
            "1002": [
                {
                    'bank': 'BANCO A',
                    'account_type': 'Ahorro',
                    'account_no': '12345',
                    'iban': '',
                    'swift': '',
                    'aba': '',
                    'regulatory_code': ''
                }
            ],
            "1003": [
                {
                    'bank': 'BANCO B',
                    'account_type': 'Corriente',
                    'account_no': '67890',
                    'iban': '',
                    'swift': '',
                    'aba': '',
                    'regulatory_code': ''
                }
            ]
        }

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_build_records_creates_correct_structures(self):
        # build_records ahora construye registros para TODOS los proveedores (upsert decide)
        records = build_records(
            self.suppliers_response,
            self.existing_suppliers,
            self.eft_by_vendor
        )

        # 1. Validar proveedores creados (Solo el nuevo 1001)
        self.assertEqual(len(records["suppliers"]), 1)
        self.assertEqual(records["suppliers"][0][0], "1001")

        # 2. Validar contactos creados (ahora incluye existentes con mail o telefono)
        self.assertEqual(len(records["contacts"]), 4)
        contact_emails = [c[2] for c in records["contacts"]]
        self.assertIn("nuevo@example.com", contact_emails)
        self.assertIn("existente_completo@example.com", contact_emails)
        self.assertIn("existente_sin_nada@example.com", contact_emails)

        # 2b. Validar teléfono en contactos
        contact_map = {c[2]: c[3] for c in records["contacts"]}
        self.assertEqual(contact_map["nuevo@example.com"], "31155512340000")
        self.assertEqual(contact_map["existente_completo@example.com"], "32055556780000")
        self.assertEqual(contact_map["existente_sin_nada@example.com"], "")
        self.assertEqual(contact_map[""], "60123456789000")

        # 2c. Proveedor existente solo con teléfono genera contacto (sin mail)
        phone_contact = [c for c in records["contacts"] if c[3] == "60123456789000"]
        self.assertEqual(len(phone_contact), 1)

        # 3. Validar direcciones creadas (PK siempre usa vendor_id = tax_id)
        self.assertEqual(len(records["addresses"]), 4)
        address_names = [a[0] for a in records["addresses"]]
        self.assertIn("0-1001:Billing", address_names)
        self.assertIn("0-1002:Billing", address_names)
        self.assertIn("0-1003:Billing", address_names)
        self.assertIn("0-1004:Billing", address_names)

        # 4. Validar cuentas bancarias creadas (PK siempre usa vendor_id = tax_id)
        self.assertEqual(len(records["bank_accounts"]), 2)
        bank_names = [ba[0] for ba in records["bank_accounts"]]
        self.assertIn("1002:12345", bank_names)
        self.assertIn("1003:67890", bank_names)
