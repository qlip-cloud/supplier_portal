# -*- coding: utf-8 -*-
"""
stale_status_alert.py (documenteme)
===================================
Nucleo puro de la alerta por estatus no definitivo (>48h).

Detecta facturas que permanecen en estados de analisis ("E", "V", "T")
durante mas de 48 horas desde su creacion (ingreso al sistema via sync).
Sirve a resources/documenteme/stale_status_alert.py, que persiste la
alerta en la child table qp_SP_Alert.

No importa Frappe: funciones puras y testables en aislamiento.
"""

from datetime import datetime, timedelta

ANALYSIS_STATES = ("E", "V", "T")

DEFAULT_THRESHOLD_HOURS = 48

_CREATION_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


def is_analysis(status):
    """True si el estatus no es definitivo ni en gestion (analisis)."""
    return status in ANALYSIS_STATES


def parse_creation(value):
    """Convierte `creation` (datetime o str) a datetime; None si no es valido."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in _CREATION_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def is_older_than(creation, now, threshold_hours=DEFAULT_THRESHOLD_HOURS):
    """True si la fecha de creacion es anterior al umbral (horas)."""
    created_at = parse_creation(creation)
    if created_at is None or now is None:
        return False
    elapsed = now - created_at
    return elapsed.total_seconds() >= threshold_hours * 3600


def should_alert(document, now, threshold_hours=DEFAULT_THRESHOLD_HOURS):
    """True si la factura esta en analisis y lleva mas del umbral de horas."""
    if not is_analysis(document.get("nvfac_esta")):
        return False
    return is_older_than(document.get("creation"), now, threshold_hours)


def build_alert_message(nvfac_nume, doc_name=None):
    """Mensaje estable de la alerta (permite dedup entre sincronizaciones)."""
    nume = nvfac_nume or doc_name or ""
    return "La factura {} lleva más de 48 horas sin revisión.".format(nume)


def cutoff_datetime(now, threshold_hours=DEFAULT_THRESHOLD_HOURS):
    """Limite inferior para filtrar creation en la consulta."""
    return now - timedelta(hours=threshold_hours)