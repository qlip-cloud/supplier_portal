# -*- coding: utf-8 -*-
import unittest
from qp_supplier_front.uses_cases.supplier.sync_all import build_records

class TestSupplierSync(unittest.TestCase):

    def setUp(self):
        # Datos de prueba para simular la respuesta de la API
        self.suppliers_response = [
            {
                "vendorId": "1001",
                "nit": "1001",
                "name": "PROVEEDOR NUEVO",
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
            }
        ]

        # Simular base de datos
        self.existing_suppliers = {
            "1002": "PROV-1002",
            "1003": "PROV-1003"
        }
        self.suppliers_with_contacts = {
            "PROV-1002"
        }
        self.suppliers_with_addresses = {
            "PROV-1002"
        }
        self.suppliers_with_bank_accounts = {
            "PROV-1002"
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

    def test_build_records_creates_correct_structures(self):
        # Ejecutar build_records con el nuevo conjunto de parámetros
        records = build_records(
            self.suppliers_response,
            self.existing_suppliers,
            self.suppliers_with_contacts,
            self.suppliers_with_addresses,
            self.suppliers_with_bank_accounts,
            self.eft_by_vendor
        )

        # 1. Validar proveedores creados (Solo el nuevo 1001)
        self.assertEqual(len(records["suppliers"]), 1)
        self.assertEqual(records["suppliers"][0][0], "1001")

        # 2. Validar contactos creados
        # Debe crear para 1001 (nuevo) y 1003 (existente sin nada).
        # No para 1002 (existente completo que ya tiene contacto).
        self.assertEqual(len(records["contacts"]), 2)
        contact_emails = [c[2] for c in records["contacts"]]
        self.assertIn("nuevo@example.com", contact_emails)
        self.assertIn("existente_sin_nada@example.com", contact_emails)
        self.assertNotIn("existente_completo@example.com", contact_emails)

        # 3. Validar direcciones creadas
        # Debe crear para 1001 (nuevo) y 1003 (existente sin nada).
        # No para 1002 (existente completo que ya tiene dirección).
        self.assertEqual(len(records["addresses"]), 2)
        address_names = [a[0] for a in records["addresses"]]
        self.assertIn("0-1001:Billing", address_names)
        self.assertIn("0-PROV-1003:Billing", address_names)
        self.assertNotIn("0-PROV-1002:Billing", address_names)

        # 4. Validar cuentas bancarias creadas
        # Debe crear para 1003 (existente sin nada).
        # No para 1002 (existente completo que ya tiene cuenta bancaria).
        self.assertEqual(len(records["bank_accounts"]), 1)
        self.assertEqual(records["bank_accounts"][0][0], "PROV-1003:67890")
