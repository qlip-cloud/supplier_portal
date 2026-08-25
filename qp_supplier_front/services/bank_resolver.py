# -*- coding: utf-8 -*-
"""
bank_resolver.py
=================
Resolución del nombre de banco recibido de un servicio externo
contra el catálogo del doctype Bank de Frappe.

Implementa una cascada de resolución en 6 niveles:
  0. Lookup en diccionario de variantes conocidas (DocType qp_SP_BankNameVariant)
  0.5. Lookup por SWIFT code (si se provee)
  1. Exact match por name (PK del doctype)
  2. Exact match normalizado (lowercase + sin tildes + sin sufijos societarios)
  3a. Fuzzy sobre nombre completo normalizado (umbral 0.82)
  3b. Fuzzy sobre nombre con prefijo/sufijo eliminado y strip simétrico (umbral 0.88)
  4. Fallback: retorna raw_name.strip() → se creará un banco nuevo

Cuando hay múltiples candidatos en niveles 2, 3a o 3b, se desambigua
eligiendo el banco con más Bank Account relacionadas (el más usado).
En empate, el de creation más antigua.
"""
import frappe
from qp_supplier_front.services.bank_normalizer import (
    normalize,
    strip_bank_prefix,
    similarity,
    FUZZY_THRESHOLD,
    FUZZY_STRIP_THRESHOLD,
)


def resolve_bank_name(raw_name: str, swift_code: str = ""):
    """
    Punto de entrada principal de la cascada de resolución.

    Args:
        raw_name:   Nombre del banco tal como llega del servicio externo.
        swift_code: Código SWIFT/BIC del banco (opcional).
                    Si se provee y se encuentra en el doctype Bank,
                    se retorna de inmediato sin continuar la cascada.

    Returns:
        El ``name`` (PK) del doctype Bank si se encontró algún match,
        o ``raw_name.strip()`` si no (se usará para crear un banco nuevo).
    """
    clean_name = raw_name.strip()

    # Nivel 0 — Diccionario de variantes conocidas (DocType qp_SP_BankNameVariant)
    match = _find_by_variant(clean_name)
    if match:
        return match

    # Nivel 0.5 — SWIFT lookup (identificador global definitivo)
    if swift_code and swift_code.strip():
        match = _find_by_swift(swift_code.strip())
        if match:
            return match

    # Nivel 1 — Exact match por name (PK)
    match = _find_exact(clean_name)
    if match:
        return match

    # Carga el catálogo una sola vez para los niveles 2, 3a, 3b
    banks = frappe.get_all("Bank", fields=["name", "bank_name"])

    if not banks:
        return clean_name

    candidate_norm = normalize(clean_name)

    # Nivel 2 — Exact match normalizado (case + tildes + sufijos societarios)
    match = _find_normalized_exact(candidate_norm, banks)
    if match:
        return match

    # Nivel 3a — Fuzzy sobre nombre completo normalizado
    match = _find_fuzzy(candidate_norm, banks, FUZZY_THRESHOLD)
    if match:
        return match

    # Nivel 3b-i — Fuzzy sobre nombre con prefijo de candidato removido + catálogo stripeado (umbral 0.88)
    stripped = strip_bank_prefix(candidate_norm, allow_no_space=True)
    if stripped:
        match = _find_fuzzy(stripped, banks, FUZZY_STRIP_THRESHOLD, strip_catalog=True)
        if match:
            return match

    # Nivel 3b-ii — Fuzzy sobre nombre completo del candidato + catálogo stripeado (umbral 0.88)
    match = _find_fuzzy(candidate_norm, banks, FUZZY_STRIP_THRESHOLD, strip_catalog=True)
    if match:
        return match

    # Nivel 4 — Fallback: crear banco nuevo con el nombre tal como viene
    return clean_name


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _find_by_variant(raw_name: str):
    """
    Busca en el doctype qp_SP_BankNameVariant por el campo raw_variant.

    Returns:
        El ``canonical_bank`` si encuentra la variante, o None.
    """
    if not frappe.db.exists("DocType", "qp_SP_BankNameVariant"):
        return None
    result = frappe.db.get_value(
        "qp_SP_BankNameVariant",
        {"raw_variant": raw_name},
        "canonical_bank"
    )
    return result or None


def _find_by_swift(swift_code: str):
    """
    Busca en el doctype Bank por el campo custom qp_swift_number.

    Returns:
        El ``name`` del banco si lo encuentra, o None.
    """
    result = frappe.db.get_value("Bank", {"qp_swift_number": swift_code}, "name")
    return result or None


def _find_exact(name: str):
    """
    Verifica si existe un Bank con ese name exacto (PK).

    Returns:
        El ``name`` si existe, o None.
    """
    exists = frappe.db.exists("Bank", name)
    return name if exists else None


def _find_normalized_exact(candidate_norm: str, banks: list):
    """
    Busca match exacto comparando el candidate normalizado contra
    los bank_name del catálogo también normalizados.

    Si hay varios candidatos (duplicados), desambigua por uso.

    Args:
        candidate_norm: Nombre entrante ya procesado por normalize().
        banks: Lista de dicts {"name": ..., "bank_name": ...} del doctype.

    Returns:
        El ``name`` del banco ganador, o None.
    """
    matches = [
        b["name"]
        for b in banks
        if normalize(b["bank_name"]) == candidate_norm
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return _disambiguate(matches)


def _find_fuzzy(candidate_norm: str, banks: list, threshold: float, strip_catalog: bool = False):
    """
    Fuzzy matching con SequenceMatcher contra todos los bancos del catálogo.

    Evalúa cada banco con el nombre normalizado completo.
    Si hay varios candidatos sobre el umbral, desambigua por uso.

    Args:
        candidate_norm: Nombre entrante normalizado (con o sin prefijo strip).
        banks:          Catálogo completo de bancos.
        threshold:      Score mínimo aceptado (FUZZY_THRESHOLD o FUZZY_STRIP_THRESHOLD).
        strip_catalog:  Si es True, aplica strip_bank_prefix con allow_no_space=False
                        a los nombres del catálogo antes de la comparación.

    Returns:
        El ``name`` del banco con mejor score sobre el umbral, o None.
    """
    scored = []

    for bank in banks:
        bank_norm = normalize(bank["bank_name"])
        if strip_catalog:
            stripped_catalog = strip_bank_prefix(bank_norm, allow_no_space=False)
            if stripped_catalog:
                bank_norm = stripped_catalog

        score = similarity(candidate_norm, bank_norm)
        if score >= threshold:
            scored.append((score, bank["name"]))

    if not scored:
        return None

    # Ordenar por score descendente
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score = scored[0][0]

    # Candidatos con el mismo score máximo (posibles duplicados)
    top_candidates = [name for score, name in scored if score == best_score]

    if len(top_candidates) == 1:
        return top_candidates[0]

    return _disambiguate(top_candidates)


def _disambiguate(candidates: list):
    """
    Desambigua entre múltiples bancos candidatos eligiendo el más usado.

    Criterio 1: Mayor cantidad de Bank Account asociadas.
    Criterio 2 (empate): Fecha de creation más antigua.

    Args:
        candidates: Lista de ``name`` (PK) del doctype Bank.

    Returns:
        El ``name`` del banco ganador.
    """
    if len(candidates) == 1:
        return candidates[0]

    # Contar Bank Accounts por cada candidato en una sola query
    usage_rows = frappe.db.sql(
        """
        SELECT bank, COUNT(*) AS cnt
        FROM `tabBank Account`
        WHERE bank IN %(banks)s
        GROUP BY bank
        """,
        {"banks": tuple(candidates)},
        as_dict=True,
    )

    usage_map = {row["bank"]: row["cnt"] for row in usage_rows}

    # Candidatos ordenados por uso descendente
    by_usage = sorted(candidates, key=lambda n: usage_map.get(n, 0), reverse=True)

    max_usage = usage_map.get(by_usage[0], 0)
    tied = [n for n in by_usage if usage_map.get(n, 0) == max_usage]

    if len(tied) == 1:
        return tied[0]

    # Desempate por creation más antigua
    creation_rows = frappe.db.sql(
        """
        SELECT name, creation
        FROM `tabBank`
        WHERE name IN %(banks)s
        ORDER BY creation ASC
        LIMIT 1
        """,
        {"banks": tuple(tied)},
        as_dict=True,
    )

    return creation_rows[0]["name"] if creation_rows else tied[0]
