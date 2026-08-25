# -*- coding: utf-8 -*-
"""
test_enrich_document_list.py
============================
Pruebas unitarias para services/enrich_document_list.py.

Aisladas de la base de datos: frappe se inyecta en sys.modules como mock.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_enrich_document_list.py -v
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

from qp_supplier_front.services.enrich_document_list import (
    build_allowance_charges,
    build_assigned_to_name,
    count_non_xml,
    enrich_document_list,
)


class TestCountNonXml(unittest.TestCase):

    def test_cuenta_solo_archivos_no_xml(self):
        files = [
            {"file_type": "XML"},
            {"file_type": "pdf"},
            {"file_type": ""},
        ]
        self.assertEqual(count_non_xml(files), 2)

    def test_sin_xml_retorna_todos(self):
        files = [{"file_type": "PDF"}, {"file_type": "XLSX"}]
        self.assertEqual(count_non_xml(files), 2)

    def test_vacio(self):
        self.assertEqual(count_non_xml([]), 0)


class TestBuildAllowanceCharges(unittest.TestCase):

    def test_acumula_running_total_con_cargo_y_descuento(self):
        charges = [
            {"reason": "Cargo envio", "amount": 100, "charge_indicator": True},
            {"reason": "Descuento", "amount": 50, "charge_indicator": False},
        ]
        result = build_allowance_charges(charges, base_total=1000)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["reason"], "Cargo envio")
        self.assertEqual(result[0]["signed_amount"], 100)
        self.assertEqual(result[0]["running_total"], 1100)
        self.assertEqual(result[1]["reason"], "Descuento")
        self.assertEqual(result[1]["signed_amount"], -50)
        self.assertEqual(result[1]["running_total"], 1050)

    def test_omite_registros_sin_monto(self):
        charges = [
            {"reason": "Sin monto", "amount": None, "charge_indicator": True},
            {"reason": "Con monto", "amount": 25, "charge_indicator": True},
        ]
        result = build_allowance_charges(charges, base_total=500)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["running_total"], 525)

    def test_reason_default_cuando_no_hay_reason(self):
        charges = [{"reason": None, "amount": 10, "charge_indicator": True}]
        result = build_allowance_charges(charges, base_total=0)
        self.assertEqual(result[0]["reason"], "Descuento/Cargo")


class TestBuildAssignedToName(unittest.TestCase):

    def test_sin_usuarios_retorna_none(self):
        frappe_mock = MagicMock()
        self.assertIsNone(build_assigned_to_name(frappe_mock, []))

    def test_construye_texto_multilinea_con_full_name(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_value.side_effect = ["Ana Perez", "Luis Gomez"]
        result = build_assigned_to_name(frappe_mock, ["U1", "U2"])
        self.assertEqual(result, "Asignado a:\n- Ana Perez\n- Luis Gomez")

    def test_usa_user_id_cuando_no_hay_full_name(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_value.return_value = None
        result = build_assigned_to_name(frappe_mock, ["U1"])
        self.assertEqual(result, "Asignado a:\n- U1")


class TestEnrichDocumentList(unittest.TestCase):

    def _make_document(self, name="DOC1", nvfac_nume="DOC1", nvfac_orde="OC111"):
        return {
            "name": name,
            "nvfac_nume": nvfac_nume,
            "nvfac_orde": nvfac_orde,
        }

    def _mock_frappe(self, detail_lines=None, allowance_charges=None, attached_files=None,
                     assignee_id=None, assigned_users=None, user_names=None):
        frappe_mock = MagicMock()
        detail_lines = detail_lines if detail_lines is not None else [
            {"nvpro_codi": "SH00086", "nvuni_desc": "UN", "nvdet_tcan": 1,
             "nvdet_valo": 1000, "nvdet_vdes": 0, "nvdet_stot": 1000}
        ]
        allowance_charges = allowance_charges if allowance_charges is not None else [
            {"reason": "Cargo envio", "amount": 100, "charge_indicator": True},
            {"reason": "Descuento", "amount": 50, "charge_indicator": False},
        ]
        attached_files = attached_files if attached_files is not None else [
            {"file_name": "doc.xml", "file_type": "XML", "file_url": "/d.xml", "file_id": "F1"}
        ]
        assigned_users = assigned_users if assigned_users is not None else [
            {"user": "user@example.com"}
        ]

        def _get_all(doctype, filters=None, fields=None, order_by=None):
            if doctype == "qp_SP_DetailLine":
                return detail_lines
            if doctype == "qp_SP_AllowanceCharge":
                return allowance_charges
            if doctype == "qp_SP_DocumentAttach":
                return attached_files
            if doctype == "qp_SP_SyncLineAssignedUser":
                return assigned_users
            return []

        frappe_mock.get_all.side_effect = _get_all
        frappe_mock.db.get_value.side_effect = lambda doctype, name, field: {
            "qp_SP_DocumentSyncLine": assignee_id,
            "User": user_names.get(name) if user_names else None,
        }.get(doctype)
        return frappe_mock

    def _run(self, document, frappe_mock):
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            enrich_document_list([document], "qp_SP_DocumentDetail")
        return document

    def test_establece_todas_las_claves_del_shape(self):
        frappe_mock = self._mock_frappe()
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertIn("detail_lines", doc)
        self.assertIn("allowance_charges", doc)
        self.assertIn("attached_files", doc)
        self.assertIn("non_xml_count", doc)
        self.assertIn("assigned_to_id", doc)
        self.assertIn("assigned_to_ids", doc)
        self.assertIn("assigned_to_name", doc)

    def test_detail_lines_con_campos_esperados(self):
        frappe_mock = self._mock_frappe()
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertEqual(doc["detail_lines"][0]["nvpro_codi"], "SH00086")
        self.assertEqual(doc["detail_lines"][0]["nvdet_stot"], 1000)

    def test_allowance_charges_con_signed_amount_y_running_total(self):
        frappe_mock = self._mock_frappe()
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        charges = doc["allowance_charges"]
        self.assertEqual(len(charges), 2)
        self.assertEqual(charges[0]["signed_amount"], 100)
        self.assertEqual(charges[0]["running_total"], 1100)
        self.assertEqual(charges[1]["signed_amount"], -50)
        self.assertEqual(charges[1]["running_total"], 1050)

    def test_non_xml_count_ignora_archivos_xml(self):
        frappe_mock = self._mock_frappe(attached_files=[
            {"file_name": "a.xml", "file_type": "XML", "file_url": "/a", "file_id": "F1"},
            {"file_name": "b.pdf", "file_type": "pdf", "file_url": "/b", "file_id": "F2"},
        ])
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertEqual(doc["attached_files"][0]["file_name"], "a.xml")
        self.assertEqual(doc["non_xml_count"], 1)

    def test_assigned_to_ids_usa_usuarios_asociados(self):
        frappe_mock = self._mock_frappe(
            assignee_id="assignee@example.com",
            assigned_users=[{"user": "u1@example.com"}],
        )
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertEqual(doc["assigned_to_id"], "assignee@example.com")
        self.assertEqual(doc["assigned_to_ids"], ["u1@example.com"])

    def test_assigned_to_ids_usuario_directo_cuando_no_hay_asociados(self):
        frappe_mock = self._mock_frappe(
            assignee_id="assignee@example.com",
            assigned_users=[],
        )
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertEqual(doc["assigned_to_ids"], ["assignee@example.com"])

    def test_assigned_to_name_construido_con_full_name(self):
        frappe_mock = self._mock_frappe(
            assigned_users=[{"user": "u1@example.com"}, {"user": "u2@example.com"}],
            user_names={"u1@example.com": "Ana Perez", "u2@example.com": "Luis Gomez"},
        )
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertEqual(
            doc["assigned_to_name"],
            "Asignado a:\n- Ana Perez\n- Luis Gomez",
        )

    def test_assigned_to_name_es_none_sin_usuarios(self):
        frappe_mock = self._mock_frappe(
            assignee_id=None,
            assigned_users=[],
        )
        document = self._make_document()
        doc = self._run(document, frappe_mock)

        self.assertIsNone(doc["assigned_to_name"])

    def test_llama_a_enrich_document_detail(self):
        frappe_mock = self._mock_frappe()
        document = self._make_document()
        with patch(
            "qp_supplier_front.services.enrich_document_list.enrich_document_detail"
        ) as mock_detail:
            with patch.dict(sys.modules, {"frappe": frappe_mock}):
                enrich_document_list([document], "qp_SP_DocumentDetail")
            mock_detail.assert_called_once_with(document)


if __name__ == "__main__":
    unittest.main()
