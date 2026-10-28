# -*- coding: utf-8 -*-
"""
super_approval.py (documenteme)
===============================
Nucleo puro de la autorizacion por superaprobador.

Una factura a credito con orden de compra y recepciones puede tener una
diferencia entre su subtotal (nvfac_stot) y la suma de las recepciones que la
respaldan. Cuando esa diferencia alcanza el umbral configurado, el usuario
normal no puede aprobarla: queda en estado PSA ("Por Autorizacion") para que
la apruebe un superaprobador.

Cada fila de configuracion define:

- threshold_amount / threshold_percentage: desde que diferencia este
  superaprobador entra en juego. 0 = criterio deshabilitado.
- limit_amount / limit_percentage: maximo que puede autorizar. 0/vacio = sin
  limite.

Los criterios de monto y porcentaje son independientes (OR): una factura es
elegible para un superaprobador si cumple el rango de monto O el de
porcentaje. El primer umbral configurado (el menor) es el que restringe al
usuario normal.

No importa Frappe: entradas/salidas son dicts/listas planas.
"""

from qp_supplier_front.uses_cases.documenteme.receipt_bank import (
    receipt_amount,
)

STATE_SUPER_APPROVAL = "PSA"

STATE_LABEL = "Por Autorización"


def _to_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_enabled(row):
    value = row.get("enabled")
    if value is None:
        return True
    return str(value).strip().lower() not in ("0", "false", "")


def normalize_rows(rows):
    """Normaliza las filas de configuracion a dicts con numeros."""
    normalized = []
    for row in (rows or []):
        if not _is_enabled(row):
            continue
        user = (row.get("user") or "").strip()
        if not user:
            continue
        normalized.append({
            "user": user,
            "threshold_amount": max(_to_float(row.get("threshold_amount")), 0.0),
            "limit_amount": max(_to_float(row.get("limit_amount")), 0.0),
            "threshold_percentage": max(
                _to_float(row.get("threshold_percentage")), 0.0
            ),
            "limit_percentage": max(
                _to_float(row.get("limit_percentage")), 0.0
            ),
        })
    return normalized


def difference(invoice_total, receipts, selected_names=None):
    """Diferencia absoluta factura vs recepciones y su porcentaje.

    selected_names: si se indica, solo se suman esas recepciones (seleccion
    manual aplicada). Sin seleccion se suman todas las recepciones recibidas.
    El porcentaje se calcula sobre nvfac_stot (0 si la factura es 0).
    """
    total = _to_float(invoice_total)
    available = [row for row in (receipts or []) if isinstance(row, dict)]

    if selected_names is None:
        selected = available
    else:
        names = set(selected_names or [])
        selected = [row for row in available if row.get("name") in names]

    receipt_total = sum(
        receipt_amount(row, total) for row in selected
    )
    amount = abs(total - receipt_total)
    percentage = (amount / total * 100.0) if total > 0 else 0.0
    return amount, percentage


def trigger_limits(rows):
    """Menor umbral de monto y de porcentaje configurados (None si no hay)."""
    amounts = [
        row["threshold_amount"] for row in (rows or [])
        if row["threshold_amount"] > 0
    ]
    percentages = [
        row["threshold_percentage"] for row in (rows or [])
        if row["threshold_percentage"] > 0
    ]
    return (
        min(amounts) if amounts else None,
        min(percentages) if percentages else None,
    )


def requires_super_approval(rows, diff_amount, diff_percent):
    """True si la diferencia alcanza el primer umbral configurado."""
    if not rows:
        return False
    amount_trigger, percentage_trigger = trigger_limits(rows)
    by_amount = (
        amount_trigger is not None and diff_amount >= amount_trigger
    )
    by_percentage = (
        percentage_trigger is not None and diff_percent >= percentage_trigger
    )
    return by_amount or by_percentage


def _matches_amount(row, diff_amount):
    if row["threshold_amount"] <= 0 or diff_amount < row["threshold_amount"]:
        return False
    return row["limit_amount"] <= 0 or diff_amount <= row["limit_amount"]


def _matches_percentage(row, diff_percent):
    threshold = row["threshold_percentage"]
    if threshold <= 0 or diff_percent < threshold:
        return False
    limit = row["limit_percentage"]
    return limit <= 0 or diff_percent <= limit


def eligible_supervisors(rows, diff_amount, diff_percent):
    """Usuarios cuyos rangos cubren la diferencia (monto OR porcentaje)."""
    users = []
    for row in (rows or []):
        if _matches_amount(row, diff_amount) or _matches_percentage(
            row, diff_percent
        ):
            if row["user"] not in users:
                users.append(row["user"])
    return users


def is_super_approver(rows, user):
    """True si el usuario esta configurado como superaprobador activo."""
    if not user:
        return False
    return any(row["user"] == user for row in (rows or []))


def classify(rows, invoice_total, receipts, selected_names=None, user=None):
    """Clasifica una factura frente a la configuracion de superaprobadores.

    Retorna un dict con la diferencia calculada, si requiere autorizacion,
    los superaprobadores elegibles, si el usuario actual esta autorizado y si
    la factura queda bloqueada (requiere autorizacion pero nadie la cubre).
    """
    diff_amount, diff_percent = difference(
        invoice_total, receipts, selected_names
    )
    required = requires_super_approval(rows, diff_amount, diff_percent)
    supervisors = (
        eligible_supervisors(rows, diff_amount, diff_percent)
        if required else []
    )
    authorized = bool(user and user in supervisors)
    return {
        "difference_amount": diff_amount,
        "difference_percentage": diff_percent,
        "requires_super_approval": required,
        "supervisors": supervisors,
        "authorized": authorized,
        "blocked": required and not supervisors,
    }
