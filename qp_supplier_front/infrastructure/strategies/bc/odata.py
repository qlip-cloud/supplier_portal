"""
odata.py (BC)
==============
Utilidades puras para construir filtros OData de Business Central.
Los campos Posting_Date de BC son Edm.Date: el literal debe ser
YYYY-MM-DD sin comillas ni hora (ej: 2026-08-05).
"""


def to_odata_date(value):
    """Normaliza una fecha/datetime a literal OData Edm.Date (YYYY-MM-DD)."""
    if value is None:
        return ""
    return str(value)[:10]
