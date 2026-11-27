# -*- coding: utf-8 -*-
"""
test_finalize_external.py
=========================
Pruebas del cierre externo de facturas documenteme (estado `FE`):

- Nucleo puro: `uses_cases/documenteme/finalize_external.py`.
- Estado bloqueado: `uses_cases/documenteme/notification_state.is_locked`.
- Guardas de sync: `services/document_sync.py`.
- Hook de inmutabilidad: `resources/documenteme/immutability.py`.
- Endpoints de cerrar/reabrir: `resources/documenteme/finalize_external.py`.
- Exclusion de flujos automaticos (auto_assign, promocion a V).

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_finalize_external.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

_sys_mods_saved = {}
for _module_name in (
    "frappe",
    "frappe.utils",
    "frappe.model",
    "frappe.model.document",
):
    _sys_mods_saved[_module_name] = sys.modules.get(_module_name)
    sys.modules[_module_name] = MagicMock()

# @frappe.whitelist() debe ser decorador identidad para poder llamar al
# endpoint directamente desde el test.
sys.modules["frappe"].whitelist = lambda *a, **k: (lambda fn: fn)
# El entorno de tests no tiene `requests`; los modulos de recursos lo importan
# a nivel de modulo.
sys.modules.setdefault("requests", MagicMock())

from qp_supplier_front.uses_cases.documenteme.finalize_external import (  # noqa: E402
    EXTERNAL_CLOSE_STATES,
    build_close_fields,
    build_reopen_fields,
    can_finalize,
    can_reopen,
    reopen_state,
)
from qp_supplier_front.uses_cases.documenteme.notification_state import (  # noqa: E402
    is_final_conflict,
    is_locked,
    resolve_state,
    resolve_ueve,
)
from qp_supplier_front.services import document_sync  # noqa: E402
from qp_supplier_front.resources.documenteme import immutability  # noqa: E402
from qp_supplier_front.resources.documenteme import finalize_external as resource  # noqa: E402
from qp_supplier_front.services import enrich_document_detail  # noqa: E402

frappe = sys.modules["frappe"]


class TestPureCore(unittest.TestCase):

    def test_estados_que_permiten_cerrar(self):
        for state in ("E", "V", "T", "SO", "SR", "PSA"):
            self.assertTrue(can_finalize(state), state)

    def test_estados_que_no_permiten_cerrar(self):
        for state in ("A", "R", "BCC", "PA", "PR", "FE", "", None):
            self.assertFalse(can_finalize(state), state)

    def test_external_close_states_no_incluye_creados_ni_finales(self):
        for state in ("BCC", "PA", "PR", "A", "R", "FE"):
            self.assertNotIn(state, EXTERNAL_CLOSE_STATES)

    def test_solo_un_fe_se_puede_reabrir(self):
        self.assertTrue(can_reopen("FE"))
        for state in ("E", "V", "A", "R", "BCC", "PA", "PR"):
            self.assertFalse(can_reopen(state), state)

    def test_build_close_fields(self):
        fields = build_close_fields("motivo", "user@x.com", "V", "2026-01-01 10:00:00")
        self.assertEqual(fields["nvfac_esta"], "FE")
        self.assertEqual(fields["qp_is_event_completed"], 1)
        self.assertEqual(fields["qp_external_previous_state"], "V")
        self.assertEqual(fields["qp_external_close_reason"], "motivo")
        self.assertEqual(fields["qp_external_closed_by"], "user@x.com")
        self.assertEqual(fields["qp_external_closed_at"], "2026-01-01 10:00:00")

    def test_reopen_state_usa_el_previo_o_cae_en_e(self):
        self.assertEqual(reopen_state("V"), "V")
        self.assertEqual(reopen_state(""), "E")
        self.assertEqual(reopen_state(None), "E")

    def test_build_reopen_fields(self):
        fields = build_reopen_fields("V")
        self.assertEqual(fields["nvfac_esta"], "V")
        self.assertEqual(fields["qp_is_event_completed"], 0)


class TestLockedState(unittest.TestCase):

    def test_is_locked_solo_fe(self):
        self.assertTrue(is_locked("FE"))
        for state in ("E", "V", "A", "R", "BCC", ""):
            self.assertFalse(is_locked(state), state)

    def test_resolve_state_no_pisa_fe_con_origen_final(self):
        for state, ueve in (("A", "033"), ("R", "031"), ("E", "030"), ("V", "")):
            self.assertEqual(resolve_state("FE", state, ueve), "FE")

    def test_resolve_ueve_congela_fe(self):
        self.assertEqual(resolve_ueve("030", "033", current_state="FE"), "030")
        self.assertEqual(resolve_ueve("", "A", current_state="FE"), "")

    def test_final_conflict_no_se_reporta_en_fe(self):
        self.assertFalse(
            is_final_conflict("FE", "", "A", "033")
        )
        self.assertFalse(
            is_final_conflict("FE", "030", "R", "031")
        )


class TestSyncGuards(unittest.TestCase):

    def setUp(self):
        frappe.reset_mock()

    def test_reconcile_ignora_fe(self):
        frappe.db.get_value.return_value = {
            "nvfac_esta": "FE",
            "nvfac_ueve": "030",
        }
        with patch.object(
            document_sync, "_get_existing_detail_name", return_value="D1"
        ):
            result = document_sync.reconcile_detail_from_line({
                "Nvfac_nume": "F1",
                "Nvpro_ndoc": "N1",
                "Nvfac_esta": "A",
                "Nvfac_ueve": "033",
            })
        self.assertIsNone(result)
        frappe.db.set_value.assert_not_called()

    def test_create_document_detail_no_toca_fe(self):
        fake_detail = MagicMock()
        fake_detail.get.side_effect = lambda key, default=None: {
            "nvfac_esta": "FE",
            "nvfac_ueve": "",
        }.get(key, default)
        frappe.get_doc.return_value = fake_detail
        with patch.object(
            document_sync, "_get_existing_detail_name", return_value="D1"
        ), patch.object(
            document_sync, "_set_document_detail_fields"
        ) as set_fields:
            result = document_sync.create_document_detail(
                "LINE", {"Nvfac_nume": "F1"}, []
            )
        self.assertIs(result, fake_detail)
        set_fields.assert_not_called()


class TestImmutabilityHook(unittest.TestCase):

    def _doc(self, previous_state, flags=None):
        doc = MagicMock()
        doc.doctype = "qp_SP_DocumentDetail"
        doc.get_doc_before_save.return_value = (
            None if previous_state is None
            else {"nvfac_esta": previous_state}
        )
        doc.flags = flags if flags is not None else MagicMock(
            allow_external_reopen=False)
        return doc

    def test_permite_save_si_el_previo_no_esta_bloqueado(self):
        frappe.reset_mock()
        immutability.validate(self._doc("E"))
        frappe.throw.assert_not_called()

    def test_bloquea_save_de_un_fe(self):
        frappe.reset_mock()
        immutability.validate(self._doc("FE"))
        frappe.throw.assert_called_once()

    def test_permite_reopen_con_flag(self):
        frappe.reset_mock()
        doc = self._doc("FE")
        doc.flags.allow_external_reopen = True
        immutability.validate(doc)
        frappe.throw.assert_not_called()

    def test_insert_sin_previo_no_bloquea(self):
        frappe.reset_mock()
        immutability.validate(self._doc(None))
        frappe.throw.assert_not_called()


class _FakeDoc(object):

    def __init__(self, state, previous_state=""):
        self.doctype = "qp_SP_DocumentDetail"
        self.name = "D1"
        self.nvfac_esta = state
        self.nvfac_nume = "F1"
        self.qp_external_previous_state = previous_state
        self.qp_is_event_completed = 0
        self.qp_event_sequence = "030"
        self.qp_event_pending_code = "030"
        self.qp_event_next_at = "2026-01-01"
        self.qp_event_attempts = 3
        self.flags = MagicMock(allow_external_reopen=False)
        self.saved = False

    def get(self, key, default=None):
        return getattr(self, key, default)

    def save(self):
        self.saved = True


class TestFinalizeResource(unittest.TestCase):

    def setUp(self):
        frappe.reset_mock()
        frappe.session.user = "admin@x.com"
        frappe.get_roles.return_value = ["Administrador Documenteme"]

    def _patched(self):
        return (
            patch.object(resource, "response"),
            patch.object(resource, "_release_claimed_receipts"),
            patch.object(resource, "resolve_open_alerts"),
            patch.object(resource, "RealTimelineAdapter"),
        )

    def test_cerrar_marca_fe_sin_crear_ni_eventos(self):
        doc = _FakeDoc("V")
        frappe.get_doc.return_value = doc
        r1, r2, r3, r4 = self._patched()
        with r1 as response, r2 as release, r3 as alerts, r4 as timeline:
            resource.finalize_external("D1", "resuelta fuera")
        self.assertEqual(doc.nvfac_esta, "FE")
        self.assertEqual(doc.qp_is_event_completed, 1)
        self.assertEqual(doc.qp_external_close_reason, "resuelta fuera")
        self.assertEqual(doc.qp_external_previous_state, "V")
        self.assertTrue(doc.saved)
        self.assertIsNone(doc.qp_event_next_at)
        release.assert_called_once()
        alerts.assert_called_once()
        timeline.return_value.add_user_assignment.assert_called_once()
        response.assert_called()
        self.assertEqual(response.call_args[0][0], 200)

    def test_cerrar_exige_motivo(self):
        doc = _FakeDoc("V")
        frappe.get_doc.return_value = doc
        with patch.object(resource, "response") as response:
            resource.finalize_external("D1", "   ")
        response.assert_called_once()
        self.assertEqual(response.call_args[0][0], 400)

    def test_cerrar_bloquea_estado_no_permitido(self):
        doc = _FakeDoc("BCC")
        frappe.get_doc.return_value = doc
        with patch.object(resource, "response") as response:
            resource.finalize_external("D1", "motivo")
        self.assertEqual(response.call_args[0][0], 400)
        self.assertFalse(doc.saved)

    def test_cerrar_permite_administrator_y_admin_documenteme(self):
        for roles in (["Administrator"], ["Administrador Documenteme"]):
            frappe.get_roles.return_value = roles
            doc = _FakeDoc("E")
            frappe.get_doc.return_value = doc
            r1, r2, r3, r4 = self._patched()
            with r1 as response, r2, r3, r4:
                resource.finalize_external("D1", "motivo")
            self.assertEqual(response.call_args[0][0], 200, roles)

    def test_cerrar_rechaza_sede_y_compras(self):
        for roles in (
            ["Administrador Sede Documenteme"],
            ["Administrador Compras Documenteme"],
        ):
            frappe.get_roles.return_value = roles
            with patch.object(resource, "response") as response:
                resource.finalize_external("D1", "motivo")
            self.assertEqual(response.call_args[0][0], 403, roles)

    def test_reabrir_restaura_estado_previo(self):
        doc = _FakeDoc("FE", previous_state="V")
        frappe.get_doc.return_value = doc
        r1, r2, r3, r4 = self._patched()
        with r1 as response, r2, r3, r4 as timeline:
            resource.reopen_external("D1", "error de cierre")
        self.assertEqual(doc.nvfac_esta, "V")
        self.assertEqual(doc.qp_is_event_completed, 0)
        self.assertTrue(doc.flags.allow_external_reopen)
        self.assertTrue(doc.saved)
        timeline.return_value.add_user_assignment.assert_called_once()
        self.assertEqual(response.call_args[0][0], 200)

    def test_reabrir_exige_fe(self):
        doc = _FakeDoc("E")
        frappe.get_doc.return_value = doc
        with patch.object(resource, "response") as response:
            resource.reopen_external("D1", "motivo")
        self.assertEqual(response.call_args[0][0], 400)
        self.assertFalse(doc.saved)


class TestAutomaticFlowsExcludeFE(unittest.TestCase):

    def setUp(self):
        frappe.reset_mock()

    def test_promocion_a_v_no_toca_fe(self):
        refs = MagicMock()
        refs.receipt_bank_for = MagicMock(side_effect=AssertionError(
            "no debe consultar el banco de una FE"))
        document = {
            "name": "D1",
            "nvfac_esta": "FE",
            "nvfac_nume": "F1",
            "nvfac_stot": 100,
        }
        enrich_document_detail._update_status_if_fully_paid(
            document, references=refs, purchase_orders=["OC1"]
        )
        refs.receipt_bank_for.assert_not_called()

    def test_auto_assign_excluye_fe(self):
        from qp_supplier_front.resources.documenteme import auto_assign
        frappe.get_all.return_value = []
        with patch(
            "qp_supplier_front.infrastructure.adapters.receipt_claim_adapter."
            "claimed_invoice_numbers",
            return_value=set(),
        ):
            candidates = auto_assign.get_candidates()
        self.assertEqual(candidates, [])
        filters = frappe.get_all.call_args[1]["filters"]
        self.assertIn("FE", filters["nvfac_esta"][1])
