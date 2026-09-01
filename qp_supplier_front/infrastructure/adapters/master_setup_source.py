# -*- coding: utf-8 -*-
"""
master_setup_source.py (infrastructure - MasterSetup adapter)
============================================================
Adaptador de configuracion de `qp_SP_MasterSetup` para el flujo documenteme.

La config del escenario (auto_approve, auto_reject, reintentos) se lee a
traves de este contrato, no con doctype hardcodeado en los resources:

  - RealMasterSetupSource: lee frappe (modo real). Replica exactamente las
    lecturas anteriores (mismo doctype/campo y defaults).
  - MemoryMasterSetupSource (simulation/master_setup_source.py): lee el store
    de la sesion (modo simulador), sin NUNCA caer a frappe.

Independencia real/simulador: la decision de simular vive SOLO en
resources/documenteme/runtime.py (documenteme_simulation); este adaptador no
expone ese campo. En modo real los consumidores usan por defecto la
implementacion Real (con el frappe de su propio modulo, patron frappe_module),
y en modo simulador el composition root inyecta la de memoria.
"""

MASTER_SETUP_DOCTYPE = "qp_SP_MasterSetup"

DEFAULT_SEDE_SOURCE = "qp_md_headquarter"
DEFAULT_REJECT_MAX_ATTEMPTS = 5
DEFAULT_REJECT_RETRY_INTERVAL = 60
DEFAULT_REJECT_EVENT_DELAY = 60


class RealMasterSetupSource(object):
    """Config de qp_SP_MasterSetup sobre frappe (modo real)."""

    def __init__(self, frappe_module=None):
        self._frappe = frappe_module

    def _frappe_module(self):
        if self._frappe is None:
            import frappe
            return frappe
        return self._frappe

    def auto_approve_enabled(self):
        frappe = self._frappe_module()
        return bool(frappe.db.get_single_value(
            MASTER_SETUP_DOCTYPE, "auto_approve"))

    def auto_reject_rule(self):
        frappe = self._frappe_module()
        return frappe.db.get_single_value(MASTER_SETUP_DOCTYPE, "auto_reject")

    def reject_config(self):
        frappe = self._frappe_module()
        return {
            "max_attempts": int(frappe.db.get_single_value(
                MASTER_SETUP_DOCTYPE, "reject_retry_max_attempts")
                or DEFAULT_REJECT_MAX_ATTEMPTS),
            "retry_interval": int(frappe.db.get_single_value(
                MASTER_SETUP_DOCTYPE, "reject_retry_interval_seconds")
                or DEFAULT_REJECT_RETRY_INTERVAL),
            "event_delay": int(frappe.db.get_single_value(
                MASTER_SETUP_DOCTYPE, "reject_event_delay_seconds")
                or DEFAULT_REJECT_EVENT_DELAY),
        }

    def sede_source_doctype(self):
        frappe = self._frappe_module()
        source = frappe.db.get_single_value(
            MASTER_SETUP_DOCTYPE, "sede_source_doctype")
        return source or DEFAULT_SEDE_SOURCE


def resolve_master_setup_source(data=None, frappe_module=None):
    """Adaptador de config: data.master_setup (memoria) o Real por defecto.

    Con data (facade) en modo simulador usa el adaptador de memoria; sin data
    (modo real) usa la implementacion real delegando al frappe inyectado.
    """
    if data is not None:
        refs = getattr(data, "master_setup", None)
        if refs is not None:
            return refs
    return RealMasterSetupSource(frappe_module=frappe_module)