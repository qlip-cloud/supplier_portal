# -*- coding: utf-8 -*-
"""
master_setup_source.py (documenteme simulation)
===============================================
Implementacion in-memory del adaptador de config de `qp_SP_MasterSetup`.

Lee SOLO del MemoryStore de la sesion (fila seed sembrada por los seeds); si
un campo no esta sembrado devuelve None/default. NUNCA hace lectura por frappe,
garantizando la independencia del modo real (la simulacion no se contamina con
la configuracion real).
"""

MASTER_SETUP_DOCTYPE = "qp_SP_MasterSetup"

DEFAULT_SEDE_SOURCE = "qp_md_headquarter"
DEFAULT_REJECT_MAX_ATTEMPTS = 5
DEFAULT_REJECT_RETRY_INTERVAL = 60
DEFAULT_REJECT_EVENT_DELAY = 60


class MemoryMasterSetupSource(object):

    def __init__(self, store):
        self._store = store

    def _value(self, field):
        rows = self._store.query(MASTER_SETUP_DOCTYPE)
        if not rows:
            return None
        return rows[0].get(field)

    def auto_approve_enabled(self):
        return bool(self._value("auto_approve"))

    def auto_reject_rule(self):
        return self._value("auto_reject")

    def reject_config(self):
        return {
            "max_attempts": int(self._value("reject_retry_max_attempts")
                                or DEFAULT_REJECT_MAX_ATTEMPTS),
            "retry_interval": int(self._value("reject_retry_interval_seconds")
                                  or DEFAULT_REJECT_RETRY_INTERVAL),
            "event_delay": int(self._value("reject_event_delay_seconds")
                               or DEFAULT_REJECT_EVENT_DELAY),
        }

    def sede_source_doctype(self):
        return self._value("sede_source_doctype") or DEFAULT_SEDE_SOURCE