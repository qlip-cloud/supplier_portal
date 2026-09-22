# -*- coding: utf-8 -*-
"""
test_auto_assign_infra.py
==========================
Pruebas unitarias para los callbacks de infraestructura de la asignacion
automatica (resources/documenteme/auto_assign.py):
  - get_receipt_total: suma el total de Purchase Receipt por qp_supplier_oc.
  - get_oc_context: valida la cadena nvfac_orde == qp_order_confirmation_no.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_assign_infra.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.resources.documenteme import auto_assign as infra  # noqa: E402
from qp_supplier_front.qp_supplier_front.doctype.qp_sp_assignmentconfig.qp_sp_assignmentconfig import (  # noqa: E402
    _normalize_headquarter,
    _normalize_oc_type,
)


class TestNormalizeHeadquarter(unittest.TestCase):

    def test_none_retorna_vacio(self):
        self.assertEqual(_normalize_headquarter(None), "")

    def test_vacio_retorna_vacio(self):
        self.assertEqual(_normalize_headquarter(""), "")

    def test_solo_codigo_se_mantiene(self):
        self.assertEqual(_normalize_headquarter("BOG"), "BOG")

    def test_codigo_con_label_se_recorta(self):
        self.assertEqual(_normalize_headquarter("BOG\nBogota (BOG)"), "BOG")

    def test_codigo_con_espacios_se_limpia(self):
        self.assertEqual(_normalize_headquarter("  BOG  \nBogota"), "BOG")


class TestNormalizeOcType(unittest.TestCase):

    OC_TYPE_ROWS = [
        {"name": "01", "oc_type": "01 INFRAESTRUCTURA"},
        {"name": "03", "oc_type": "03 IT Y EQUIPOS ELECTRONICOS"},
    ]

    def test_none_retorna_vacio(self):
        self.assertEqual(_normalize_oc_type(None, self.OC_TYPE_ROWS), "")

    def test_vacio_retorna_vacio(self):
        self.assertEqual(_normalize_oc_type("", self.OC_TYPE_ROWS), "")

    def test_codigo_name_se_mantiene(self):
        self.assertEqual(_normalize_oc_type("01", self.OC_TYPE_ROWS), "01")

    def test_label_concat_se_resuelve_al_codigo(self):
        self.assertEqual(
            _normalize_oc_type("01 INFRAESTRUCTURA", self.OC_TYPE_ROWS), "01"
        )

    def test_sin_rows_devuelve_valor(self):
        self.assertEqual(_normalize_oc_type("01", []), "01")

    def test_valor_inexistente_se_mantiene(self):
        self.assertEqual(_normalize_oc_type("99", self.OC_TYPE_ROWS), "99")


class TestGetReceiptTotal(unittest.TestCase):

    def _run(self, frappe_mock, purchase_order_number):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_receipt_total(purchase_order_number)

    def test_suma_totales_de_purchase_receipt_por_supplier_oc(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [
            {"name": "R1", "total": 400, "posting_date": "2026-01-01", "qp_invoice": None},
            {"name": "R2", "total": 600, "posting_date": "2026-01-02", "qp_invoice": None},
        ]

        total = self._run(frappe_mock, "OC111")

        self.assertEqual(total, 1000)
        frappe_mock.get_all.assert_called_once_with(
            "Purchase Receipt",
            filters={"qp_supplier_oc": "OC111"},
            fields=["name", "total", "posting_date", "qp_invoice"],
        )

    def test_sin_recibos_retorna_none(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        self.assertIsNone(self._run(frappe_mock, "OC111"))

    def test_sin_oc_retorna_none(self):
        self.assertIsNone(self._run(MagicMock(), None))

    def test_recibos_sin_total_no_rompen_la_suma(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [{"total": None}, {"total": 200}]
        self.assertEqual(self._run(frappe_mock, "OC111"), 200)


class TestGetReceiptBank(unittest.TestCase):

    def _run(self, frappe_mock, purchase_order_number):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_receipt_bank(purchase_order_number)

    def test_devuelve_filas_con_amount_date_y_qp_invoice(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [
            {"name": "R1", "total": 400, "posting_date": "2026-01-01", "qp_invoice": None},
            {"name": "R2", "total": 600, "posting_date": "2026-01-02", "qp_invoice": "FAC001"},
        ]

        bank = self._run(frappe_mock, "OC111")

        self.assertEqual(bank, [
            {"name": "R1", "amount": 400, "date": "2026-01-01", "qp_invoice": None},
            {"name": "R2", "amount": 600, "date": "2026-01-02", "qp_invoice": "FAC001"},
        ])
        frappe_mock.get_all.assert_called_once_with(
            "Purchase Receipt",
            filters={"qp_supplier_oc": "OC111"},
            fields=["name", "total", "posting_date", "qp_invoice"],
        )

    def test_sin_recibos_retorna_lista_vacia(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        self.assertEqual(self._run(frappe_mock, "OC111"), [])

    def test_sin_oc_retorna_lista_vacia(self):
        self.assertEqual(self._run(MagicMock(), None), [])


class TestGetOCContext(unittest.TestCase):

    def _mock_frappe(self, po_exists=True, values=None):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = po_exists
        frappe_mock.db.get_value.return_value = values or (
            "01", "BOG", "OC111"
        )
        return frappe_mock

    def _run(self, frappe_mock, purchase_order_number):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_oc_context(purchase_order_number)

    def test_devuelve_contexto_cuando_cadena_coincide(self):
        frappe_mock = self._mock_frappe()
        ctx = self._run(frappe_mock, "OC111")
        self.assertEqual(ctx, {"oc_type": "01", "headquarter": "BOG"})

    def test_sin_oc_retorna_none(self):
        self.assertIsNone(self._run(self._mock_frappe(), None))

    def test_oc_inexistente_retorna_none(self):
        frappe_mock = self._mock_frappe(po_exists=False)
        self.assertIsNone(self._run(frappe_mock, "OC111"))

    def test_cadena_rota_retorna_none(self):
        frappe_mock = self._mock_frappe(values=("01", "BOG", "OC999"))
        self.assertIsNone(self._run(frappe_mock, "OC111"))


class TestLoadAssignmentRows(unittest.TestCase):

    def _mock_get_all(self, configs, role_rows_map=None):
        frappe_mock = MagicMock()
        role_rows_map = role_rows_map or {}

        def _get_all(doctype, **kwargs):
            if doctype == "qp_SP_OCType":
                return [
                    {"name": "01", "oc_type": "01 INFRAESTRUCTURA"},
                    {"name": "03", "oc_type": "03 IT Y EQUIPOS ELECTRONICOS"},
                ]
            if doctype == "qp_SP_AssignmentConfig":
                return configs
            if doctype == "qp_SP_AssignmentConfigUser":
                parent = kwargs["filters"]["parent"]
                return [
                    {"user_email": "a@x.com"},
                    {"user_email": "b@x.com"},
                ] if parent == "CONF1" else []
            if doctype == "qp_SP_AssignmentConfigRole":
                parent = kwargs["filters"]["parent"]
                return role_rows_map.get(parent, [])
            return []

        frappe_mock.get_all.side_effect = _get_all
        return frappe_mock

    def test_codigo_con_label_combinado_se_normaliza(self):
        frappe_mock = self._mock_get_all([
            {"name": "CONF1", "headquarter": "BOG\nBogota (BOG)", "oc_type": "01 INFRAESTRUCTURA"},
        ])

        with patch.object(infra, "frappe", frappe_mock):
            rows = infra._load_assignment_rows()

        self.assertEqual(rows, [{
            "headquarter": "BOG",
            "oc_type": "01",
            "user_emails": ["a@x.com", "b@x.com"],
            "user_roles": [],
        }])

    def test_headquarter_solo_codigo_se_mantiene(self):
        frappe_mock = self._mock_get_all([
            {"name": "CONF2", "headquarter": "CAL", "oc_type": "03"},
        ])

        with patch.object(infra, "frappe", frappe_mock):
            rows = infra._load_assignment_rows()

        self.assertEqual(rows, [{
            "headquarter": "CAL",
            "oc_type": "03",
            "user_emails": [],
            "user_roles": [],
        }])

    def test_carga_roles_del_child(self):
        frappe_mock = self._mock_get_all(
            [{"name": "CONF1", "headquarter": "BOG", "oc_type": "01"}],
            role_rows_map={"CONF1": [{"role": "Alpla Compras"}, {"role": "Alpla Finanzas"}]},
        )

        with patch.object(infra, "frappe", frappe_mock):
            rows = infra._load_assignment_rows()

        self.assertEqual(rows, [{
            "headquarter": "BOG",
            "oc_type": "01",
            "user_emails": ["a@x.com", "b@x.com"],
            "user_roles": ["Alpla Compras", "Alpla Finanzas"],
        }])

    def test_no_aplica_se_mantiene_sin_normalizar(self):
        frappe_mock = self._mock_get_all([
            {"name": "CONF3", "headquarter": "CAL", "oc_type": "No aplica"},
        ])

        with patch.object(infra, "frappe", frappe_mock):
            rows = infra._load_assignment_rows()

        self.assertEqual(rows, [{
            "headquarter": "CAL",
            "oc_type": "No aplica",
            "user_emails": [],
            "user_roles": [],
        }])


class TestGetAssigneeEmails(unittest.TestCase):

    OC_TYPE_ROWS = [
        {"name": "01", "oc_type": "01 INFRAESTRUCTURA", "is_inventariable": 1},
        {"name": "03", "oc_type": "03 IT Y EQUIPOS ELECTRONICOS", "is_inventariable": 0},
    ]

    ASSIGNMENT_ROWS = [
        {"headquarter": "BOG", "oc_type": "01", "user_emails": ["a@x.com", "b@x.com"]},
        {"headquarter": "BOG", "oc_type": "03", "user_emails": ["c@x.com"]},
    ]

    def _run(self, frappe_mock, oc_type, headquarter):
        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", return_value=self.ASSIGNMENT_ROWS):
            return infra.get_assignee_emails(oc_type, headquarter)

    def test_inventariable_sede_valida_retorna_emails(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = self.OC_TYPE_ROWS
        with patch.object(infra, "sede_exists", return_value=True) as sede_exists_mock:
            emails = self._run(frappe_mock, "01", "BOG")

        self.assertEqual(emails, ["a@x.com", "b@x.com"])
        sede_exists_mock.assert_called_once_with("BOG")

    def test_inventariable_sede_inexistente_retorna_none(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = self.OC_TYPE_ROWS
        with patch.object(infra, "sede_exists", return_value=False):
            emails = self._run(frappe_mock, "01", "BOG")

        self.assertIsNone(emails)

    def test_no_inventariable_no_valida_sede(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = self.OC_TYPE_ROWS
        with patch.object(infra, "sede_exists", return_value=False) as sede_exists_mock:
            emails = self._run(frappe_mock, "03", "BOG")

        self.assertEqual(emails, ["c@x.com"])
        sede_exists_mock.assert_not_called()

    def test_oc_type_sin_configurar_retorna_none(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = self.OC_TYPE_ROWS
        with patch.object(infra, "sede_exists", return_value=True):
            emails = self._run(frappe_mock, "99", "BOG")

        self.assertIsNone(emails)

    def test_config_con_valor_combinado_normaliza_y_resuelve(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [
            self.OC_TYPE_ROWS,
            [{"name": "CONF1", "headquarter": "BOG\nBogota (BOG)", "oc_type": "01 INFRAESTRUCTURA"}],
            [{"user_email": "a@x.com"}, {"user_email": "b@x.com"}],
            [],
        ]

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "sede_exists", return_value=True):
            emails = infra.get_assignee_emails("01", "BOG")

        self.assertEqual(emails, ["a@x.com", "b@x.com"])

    def test_roles_de_la_fila_se_resuelven_y_se_mezclan(self):
        rows = [
            {"headquarter": "BOG", "oc_type": "03", "user_emails": ["c@x.com"],
             "user_roles": ["Alpla Finanzas"]},
        ]
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [
            self.OC_TYPE_ROWS,
            ["rol@x.com"],
            ["rol@x.com"],
        ]

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", return_value=rows):
            emails = infra.get_assignee_emails("03", "BOG")

        self.assertEqual(emails, ["c@x.com", "rol@x.com"])

    def test_no_aplica_resuelve_sin_validar_sede(self):
        rows = [
            {"headquarter": "CAL", "oc_type": "No aplica", "user_emails": ["wild@x.com"],
             "user_roles": []},
        ]
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [self.OC_TYPE_ROWS]

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", return_value=rows), \
                patch.object(infra, "sede_exists", return_value=False) as sede_exists_mock:
            emails = infra.get_assignee_emails("03", "CAL")

        self.assertEqual(emails, ["wild@x.com"])
        sede_exists_mock.assert_not_called()


class TestResolveRoleUsers(unittest.TestCase):

    def _run(self, frappe_mock, roles):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.resolve_role_users(roles)

    def test_resuelve_usuarios_habilitados_por_rol(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [
            ["c@x.com", "d@x.com", "off@x.com"],
            ["c@x.com", "d@x.com"],
        ]

        emails = self._run(frappe_mock, ["Alpla Compras"])

        self.assertEqual(emails, ["c@x.com", "d@x.com"])
        frappe_mock.get_all.assert_any_call(
            "Has Role",
            filters={"role": "Alpla Compras", "parenttype": "User"},
            pluck="parent",
        )

    def test_dedupe_usuarios_entre_roles(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [
            ["c@x.com"],
            ["c@x.com"],
            ["d@x.com"],
            ["d@x.com"],
        ]

        emails = self._run(frappe_mock, ["Alpla Compras", "Alpla Finanzas"])

        self.assertEqual(emails, ["c@x.com", "d@x.com"])

    def test_sin_roles_no_consulta(self):
        frappe_mock = MagicMock()
        emails = self._run(frappe_mock, [])
        self.assertEqual(emails, [])
        frappe_mock.get_all.assert_not_called()

    def test_rol_sin_usuarios_habilita_skips(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [["off@x.com"], []]
        self.assertEqual(self._run(frappe_mock, ["Rol Vacio"]), [])


if __name__ == "__main__":
    unittest.main()
