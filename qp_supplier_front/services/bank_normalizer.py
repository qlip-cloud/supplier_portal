# -*- coding: utf-8 -*-
"""
bank_normalizer.py
==================
Funciones puras de normalización y similitud para nombres de bancos.

Sin efectos secundarios ni dependencias de Frappe.
Todos los inputs/outputs son strings inmutables.
"""
import re
import unicodedata
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Umbrales de similitud
# ---------------------------------------------------------------------------
FUZZY_THRESHOLD = 0.82
"""Umbral para match fuzzy sobre nombre completo normalizado."""

FUZZY_STRIP_THRESHOLD = 0.88
"""
Umbral más estricto para match fuzzy luego de eliminar prefijos.
Mayor exigencia para reducir falsos positivos (ej. 'america' vs 'Bank of America').
"""

# ---------------------------------------------------------------------------
# Patrón de prefijos genéricos bancarios multi-idioma
# Ordenados de más específico (más largo) a menos específico.
# ---------------------------------------------------------------------------
_BANK_PREFIX_RE = re.compile(
    r"^("
    # Francés
    r"banque\s+de\s+la\s+|banque\s+du\s+|banque\s+de\s+|banque\s+"
    # Español
    r"|banco\s+de\s+la\s+|banco\s+del\s+|banco\s+de\s+|banco\s+"
    # Inglés
    r"|bank\s+of\s+the\s+|bank\s+of\s+|bank\s+"
    # Italiano / Portugués
    r"|banca\s+di\s+|banca\s+|banco\s+do\s+|banco\s+da\s+"
    r")",
    flags=re.IGNORECASE,
)

_BANK_PREFIX_NOSPACE_RE = re.compile(
    r"^("
    r"banque|banco|bank|banca"
    r")",
    flags=re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Patrón de sufijos societarios/legales comunes
# ---------------------------------------------------------------------------
_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(s\.?\s*a\.?\s*s?\.?|ltda?\.?|inc\.?|corp\.?|llc\.?|s\.?\s*c\.?|e\.?\s*a\.?\s*t\.?|ltd\.?)$",
    flags=re.IGNORECASE,
)

_MIN_STRIP_RESULT_LEN = 3
"""Longitud mínima del resultado tras eliminar prefijo para ser considerado válido."""


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    """
    Normaliza un nombre de banco:
      - Elimina espacios extremos
      - Convierte a minúsculas
      - Elimina tildes y diacríticos
      - Elimina sufijos societarios (S.A., S.A.S., LTDA, etc.)

    NO elimina prefijos bancarios ("banco", "bank", etc.).

    Args:
        name: Nombre de banco tal como se recibe (cualquier case/acentos).

    Returns:
        Cadena normalizada en minúsculas sin acentos ni sufijos legales.
    """
    name = name.strip()
    nfd_form = unicodedata.normalize("NFD", name)
    without_accents = "".join(
        ch for ch in nfd_form if unicodedata.category(ch) != "Mn"
    )
    normalized = without_accents.lower().strip()
    return _LEGAL_SUFFIX_RE.sub("", normalized).strip()


def strip_bank_prefix(normalized_name: str, allow_no_space: bool = False) -> str | None:
    """
    Intenta eliminar el prefijo genérico bancario de un nombre ya normalizado.

    Solo actúa sobre el nombre entrante del servicio externo;
    nunca debe aplicarse a nombres del doctype Bank.

    Args:
        normalized_name: Nombre ya procesado por `normalize()`.
        allow_no_space:  Si es True, permite eliminar prefijos que estén pegados
                         al nombre del banco (ej. "bancodavivienda" -> "davivienda").

    Returns:
        Nombre sin prefijo si el resultado tiene al menos
        ``_MIN_STRIP_RESULT_LEN`` caracteres, o ``None`` si:
          - No se encontró ningún prefijo a eliminar.
          - El resultado tras el strip es demasiado corto.
    """
    # Intentar primero con el regex estándar (que exige espacio)
    stripped = _BANK_PREFIX_RE.sub("", normalized_name).strip()

    if stripped != normalized_name:
        if len(stripped) >= _MIN_STRIP_RESULT_LEN:
            return stripped
        return None

    # Si no hubo match con espacio e indicamos allow_no_space y no hay espacios en el nombre
    if allow_no_space and " " not in normalized_name:
        stripped_nospace = _BANK_PREFIX_NOSPACE_RE.sub("", normalized_name).strip()
        if stripped_nospace != normalized_name:
            if len(stripped_nospace) >= _MIN_STRIP_RESULT_LEN:
                return stripped_nospace

    return None


def similarity(a: str, b: str) -> float:
    """
    Calcula el coeficiente de similitud entre dos cadenas ya normalizadas.

    Usa ``difflib.SequenceMatcher`` (stdlib Python, sin dependencias externas).

    Args:
        a: Primera cadena normalizada.
        b: Segunda cadena normalizada.

    Returns:
        Float entre 0.0 (sin similitud) y 1.0 (idénticas).
    """
    return SequenceMatcher(None, a, b).ratio()

