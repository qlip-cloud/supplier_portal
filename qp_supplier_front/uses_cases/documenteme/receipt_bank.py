# -*- coding: utf-8 -*-
"""
receipt_bank.py (documenteme)
=============================
Nucleo puro del "banco de recepciones" (receipt bank) para la aprobacion
de facturas de credito documenteme.

Una factura de credito se respalda en una combinacion exacta de recepciones
de compra (Purchase Receipt) aun NO consumidas por otra factura aprobada.
Este modulo provee las funciones puras para:

- filtrar el pool no consumido (qp_invoice vacio),
- resolver la combinacion exacta para una factura (dos niveles: acumulacion
  cronologica O(n) y subset-sum DFS acotado),
- empaquetar un grupo de facturas de una misma orden de compra maximizando
  la cantidad de facturas completadas (small set-packing con degradacion
  greedy por orden de llegada).

No importa Frappe: todas las entradas/salidas son dicts/listas planas.
"""

DEFAULT_EPSILON = 0.01

MAX_INVOICES_PER_OC_GROUP = 4

MAX_MATCHES_PER_INVOICE = 8

NODE_BUDGET = 2000

MATCHES_TO_COLLECT = 8


def _to_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _amount(receipt):
    return _to_float(receipt.get("amount")) if isinstance(receipt, dict) else 0.0


def _sort_by_date_name(receipts):
    return sorted(
        receipts,
        key=lambda r: (str(r.get("date") or ""), str(r.get("name") or "")),
    )


def are_close(a, b, epsilon):
    """True si dos montos son iguales dentro de la tolerancia epsilon."""
    return abs(_to_float(a) - _to_float(b)) <= epsilon


def unconsumed_receipts(receipts):
    """Recepciones cuyo qp_invoice esta vacio (aun no consumidas)."""
    return [r for r in (receipts or []) if not r.get("qp_invoice")]


def _chronological_skip(receipts, invoice_total, epsilon):
    """Nivel 1: acumula en orden cronologico saltando lo que exceda el total.

    Retorna el subconjunto acumulado si su suma coincide (epsilon) con el
    total de la factura; None en caso contrario.
    """
    matched = []
    total = 0.0
    for receipt in receipts:
        amount = _amount(receipt)
        if total + amount > invoice_total + epsilon:
            continue
        matched.append(receipt)
        total += amount
    if are_close(total, invoice_total, epsilon):
        return matched
    return None


def _exact_subset(receipts, invoice_total, epsilon, max_matches, node_budget):
    """Nivel 2: subset-sum DFS acotado que busca una combinacion exacta.

    Retorna la lista de receipts que suman invoice_total (epsilon) o None.
    """
    budget = {"left": node_budget}
    found = [None]

    def search(start, remaining, chosen):
        if budget["left"] <= 0 or found[0] is not None:
            return
        budget["left"] -= 1
        if are_close(remaining, 0.0, epsilon):
            found[0] = list(chosen)
            return
        if remaining < -epsilon or start >= len(receipts):
            return
        if len(chosen) >= max_matches:
            return
        for index in range(start, len(receipts)):
            amount = _amount(receipts[index])
            if amount > remaining + epsilon:
                continue
            chosen.append(receipts[index])
            search(index + 1, remaining - amount, chosen)
            chosen.pop()
            if found[0] is not None:
                return

    search(0, invoice_total, [])
    return found[0]


def solve_receipt_bank(invoice_total, receipts, epsilon):
    """Resuelve la combinacion exacta de recepciones para una factura.

    Ignora las recepciones ya consumidas y busca primero con la acumulacion
    cronologica O(n) y, si no hay coincidencia, con un subset-sum DFS acotado.

    Retorna la lista de receipts que suman invoice_total (epsilon) o None.
    """
    bank = unconsumed_receipts(receipts)
    if not bank:
        return None
    ordered = _sort_by_date_name(bank)
    level1 = _chronological_skip(ordered, _to_float(invoice_total), epsilon)
    if level1:
        return level1
    exact = _exact_subset(
        ordered,
        _to_float(invoice_total),
        epsilon,
        MAX_MATCHES_PER_INVOICE,
        NODE_BUDGET,
    )
    return exact if exact else None


def _collect_matches(invoice_total, receipts, epsilon, max_matches, budget):
    """Enumera (acotado) subconjuntos que suman invoice_total con epsilon."""
    matches = []

    def search(start, remaining, chosen):
        if budget["left"] <= 0 or len(matches) >= MATCHES_TO_COLLECT:
            return
        budget["left"] -= 1
        if len(chosen) > max_matches:
            return
        if are_close(remaining, 0.0, epsilon):
            matches.append(list(chosen))
            return
        if remaining < -epsilon or start >= len(receipts):
            return
        for index in range(start, len(receipts)):
            amount = _amount(receipts[index])
            if amount > remaining + epsilon:
                continue
            chosen.append(receipts[index])
            search(index + 1, remaining - amount, chosen)
            chosen.pop()
            if len(matches) >= MATCHES_TO_COLLECT:
                return

    search(0, _to_float(invoice_total), [])
    return matches


def _without(receipts, matched):
    used = {r.get("name") for r in matched}
    return [r for r in receipts if r.get("name") not in used]


def _greedy_by_arrival(invoices, receipts, epsilon, max_matches_per_invoice):
    """Degradacion: asigna por orden de llegada con solve_receipt_bank."""
    allocation = {}
    remaining = list(receipts)
    for invoice in invoices:
        total = _to_float(invoice.get("nvfac_stot"))
        matched = solve_receipt_bank(total, remaining, epsilon)
        if matched is None:
            continue
        allocation[invoice.get("nvfac_nume")] = matched
        remaining = _without(remaining, matched)
    return allocation


def _pack_exact(invoices, receipts, epsilon, max_matches_per_invoice, node_budget):
    """Small set-packing: maximiza facturas completadas con busqueda acotada."""
    budget = {"left": node_budget}
    best = {"allocation": {}, "count": -1}

    def search(index, remaining, allocation):
        if budget["left"] <= 0:
            return
        budget["left"] -= 1

        completed = len(allocation)
        if completed > best["count"]:
            best["count"] = completed
            best["allocation"] = dict(allocation)

        if index >= len(invoices) or best["count"] == len(invoices):
            return

        search(index + 1, remaining, allocation)

        invoice = invoices[index]
        total = _to_float(invoice.get("nvfac_stot"))
        matches = _collect_matches(
            total, remaining, epsilon, max_matches_per_invoice, budget
        )
        for matched in matches:
            if budget["left"] <= 0:
                return
            new_allocation = dict(allocation)
            new_allocation[invoice.get("nvfac_nume")] = matched
            search(index + 1, _without(remaining, matched), new_allocation)

    search(0, receipts, {})
    return best["allocation"]


def pack_oc_group(invoices, receipts, epsilon, max_invoices, max_matches_per_invoice):
    """Asigna recepciones a las facturas de una orden de compra.

    Retorna un dict {nvfac_nume: [receipts]} que maximiza la cantidad de
    facturas completadas. Degrada a greedy por orden de llegada cuando el
    grupo excede max_invoices o el presupuesto de busqueda.
    """
    bank = unconsumed_receipts(receipts)
    ordered = _sort_by_date_name(bank)
    if not invoices or not ordered:
        return {}
    if len(invoices) > max_invoices:
        return _greedy_by_arrival(invoices, ordered, epsilon, max_matches_per_invoice)

    exact = _pack_exact(invoices, ordered, epsilon, max_matches_per_invoice, NODE_BUDGET)
    if exact:
        return exact
    return _greedy_by_arrival(invoices, ordered, epsilon, max_matches_per_invoice)
