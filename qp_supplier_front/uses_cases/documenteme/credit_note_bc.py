# -*- coding: utf-8 -*-
"""
credit_note_bc.py (documenteme)
===============================
Nucleo puro del armado de lineas de una Nota Credito para Business Central.

La NC no tiene OC ni recepciones propias: sus productos se toman de las
lineas de recepcion / orden de compra de la factura de compra referenciada.
La cantidad y el precio salen del detalle de la NC. Este modulo empareja
ambas fuentes y no importa Frappe, por lo que se testea en aislamiento.
"""


def _normalize(value):
    return " ".join(str(value or "").strip().lower().split())


def _line_candidates(nc_line, bank_lines):
    """Candidatas del banco para una linea de la NC.

    Primero restringe por la recepcion / orden que declare la linea de la NC
    (si el banco tiene lineas con ese dato).
    """
    candidates = list(bank_lines or [])
    receiving = (nc_line.get("receipt") or "").strip()
    order = (nc_line.get("order") or "").strip()
    if receiving:
        filtered = [
            line for line in candidates
            if (line.get("receiving_no") or "") == receiving
        ]
        if filtered:
            candidates = filtered
    if order:
        filtered = [
            line for line in candidates
            if (line.get("order_no") or "") == order
        ]
        if filtered:
            candidates = filtered
    return candidates


def _match_exact(nc_line, candidates, used):
    """Empareja por codigo y luego por nombre/descripcion (sin usar usadas)."""
    available = [line for line in candidates if id(line) not in used]

    code = _normalize(nc_line.get("item_code"))
    if code:
        for line in available:
            if _normalize(line.get("item_code")) == code:
                return line

    description = _normalize(nc_line.get("description"))
    if description:
        for line in available:
            if (
                _normalize(line.get("item_name")) == description
                or _normalize(line.get("description")) == description
            ):
                return line
    return None


def _unmatched_error(index, nc_line):
    return (
        "No se pudo resolver el producto BC de la linea {} de la nota "
        "credito ({}): no coincide con la recepcion/OC de la referencia"
    ).format(index, nc_line.get("item_code") or "-")


def resolve_credit_note_lines(nc_lines, bank_lines):
    """Arma las lineas BC de una NC a partir de su detalle y del banco.

    nc_lines: [{item_code, description, qty, rate, receipt, order}]
    bank_lines: [{item_code, item_name, description, receiving_no, order_no}]

    Empareja por codigo, por nombre/descripcion y, si quedan la misma
    cantidad de lineas y de candidatas, por orden (posicional). Si una linea
    no se puede emparejar de forma determinista, retorna error y no se envia
    la nota.

    Retorna (payload_lines, error). Cada payload line tiene la forma del
    endpoint BC de NC: {item_code, qty, rate, type}.
    """
    if not nc_lines:
        return [], "La nota credito no tiene lineas para enviar"
    if not bank_lines:
        return [], (
            "La factura de compra referenciada no tiene recepciones ni orden "
            "de compra para tomar los productos"
        )

    matches = [None] * len(nc_lines)
    used = set()
    for index, nc_line in enumerate(nc_lines):
        candidates = _line_candidates(nc_line, bank_lines)
        match = _match_exact(nc_line, candidates, used)
        if match is not None:
            matches[index] = match
            used.add(id(match))

    unmatched = [i for i, match in enumerate(matches) if match is None]
    unused = [line for line in bank_lines if id(line) not in used]
    if len(unmatched) == len(unused) and unmatched:
        for index, line in zip(unmatched, unused):
            matches[index] = line
            used.add(id(line))
    elif unmatched:
        return [], _unmatched_error(unmatched[0] + 1, nc_lines[unmatched[0]])

    payload = []
    for nc_line, match in zip(nc_lines, matches):
        payload.append({
            "item_code": match.get("item_code") or "",
            "qty": nc_line.get("qty") or 0,
            "rate": nc_line.get("rate") or 0,
            "type": "Item",
        })
    return payload, ""
