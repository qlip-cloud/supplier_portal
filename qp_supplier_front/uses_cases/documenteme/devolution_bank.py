# -*- coding: utf-8 -*-
"""
devolution_bank.py (documenteme)
================================
Nucleo puro del "banco de devoluciones" para las notas de credito tipo 5 GP.

Una NC tipo 5 (Nvtip_docu == "C" que referencia una factura de compra tipo
1/2) no tiene OC propia: sus lineas se cargan desde el detalle de la propia
NC (homologado) y la informacion de orden/recibo (noRecepcion/noPedido) se
toma de la factura de compra que referencia. Las devoluciones se asignan a un
banco de lineas de la referencia:

- Referencia tipo 1 (Envio): banco desde las recepciones de la referencia
  (Purchase Receipt Item). Cada linea lleva receiving_no (recibo) y order_no.
- Referencia tipo 2 (Envio Factura): banco desde las lineas de la OC de la
  referencia (Purchase Order Item). La linea lleva solo el order_no.

El banco se consume con cada devolucion aprobada: la disponibilidad por linea
es la cantidad original menos lo ya devuelto (qp_SP_Devolution). Si una
devolucion excede la cantidad disponible se detecta un excedente (alerta);
en aprobacion manual forzada se envia igual tras confirmacion del usuario.

Este modulo NO importa Frappe: recibe dicts/listas planas.
"""


def _float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_receipt_bank(receipt_items):
    """Banco desde Purchase Receipt Item de la referencia (tipo 1).

    Cada item proveniente de `get_lines_from_receipts` ya trae item_code,
    qty, rate, idx, uom, receiving_no (recibo) y order_no. Se conserva una
    fila por linea de recepcion (no se consolida), porque la devolucion se
    asocia a una linea puntual de la recepcion.

    Retorna [{item_code, qty, idx, receiving_no, order_no}].
    """
    bank = []
    for item in (receipt_items or []):
        item_code = item.get("item_code")
        qty = _float(item.get("qty"))
        if not item_code or qty <= 0:
            continue
        bank.append({
            "item_code": item_code,
            "qty": qty,
            "idx": int(item.get("idx") or 0),
            "receiving_no": item.get("receiving_no") or "",
            "order_no": item.get("order_no") or "",
        })
    return bank


def build_po_bank(po_items, order_no=""):
    """Banco desde las lineas de la OC de la referencia (tipo 2).

    Cada Purchase Order Item aporta item_code, qty e idx (noLineaRecepcion);
    no hay recepcion, por lo que receiving_no queda vacio y order_no es la OC
    de la referencia.

    Retorna [{item_code, qty, idx, receiving_no:"", order_no}].
    """
    bank = []
    for item in (po_items or []):
        item_code = item.get("item_code")
        qty = _float(item.get("qty"))
        if not item_code or qty <= 0:
            continue
        bank.append({
            "item_code": item_code,
            "qty": qty,
            "idx": int(item.get("idx") or 0),
            "receiving_no": "",
            "order_no": order_no or (item.get("order_no") or ""),
        })
    return bank


def _line_key(item_code, receiving_no, order_no):
    return (str(item_code or ""), str(receiving_no or ""), str(order_no or ""))


def apply_consumed(bank_lines, consumed_rows):
    """Resta de cada linea del banco lo ya devuelto (qp_SP_Devolution).

    consumed_rows: [{item_code, qty, receiving_no, order_no}]. La cantidad
    disponible de cada linea es qty - suma de lo consumido por esa linea.
    Nunca baja de 0.
    """
    used = {}
    for row in (consumed_rows or []):
        key = _line_key(
            row.get("item_code"), row.get("receiving_no"), row.get("order_no")
        )
        used[key] = used.get(key, 0.0) + _float(row.get("qty"))

    available = []
    for line in (bank_lines or []):
        key = _line_key(
            line.get("item_code"), line.get("receiving_no"), line.get("order_no")
        )
        remaining = _float(line.get("qty")) - used.get(key, 0.0)
        available.append(dict(line, qty=max(remaining, 0.0)))
    return available


def allocate_devolution(nc_lines, bank_lines):
    """Asigna las lineas de la NC tipo 5 a las lineas del banco disponible.

    nc_lines: [{item_code, qty}] deduplicadas/consolidadas por producto.
    bank_lines: banco ya con `qty` = cantidad disponible (apply_consumed).

    Asignacion greedy por linea en orden: para cada linea de la NC se consume
    de las lineas del banco del mismo item hasta cubrir la cantidad.

    Retorna (assigned, excess):
    - assigned: [{item_code, qty, idx, receiving_no, order_no}] (una por linea
      de banco consumida; una NC puede dividirse entre varias lineas del
      banco). El idx es el noLineaRecepcion de la linea de la OC/recepcion.
    - excess: [{item_code, qty}] cantidad no cubierta por el banco.
    """
    by_item = {}
    for line in (bank_lines or []):
        by_item.setdefault(line.get("item_code"), []).append(line)

    assigned = []
    excess = []
    for nc_line in (nc_lines or []):
        item_code = nc_line.get("item_code")
        qty = _float(nc_line.get("qty"))
        if not item_code or qty <= 0:
            continue
        remaining = qty
        for bank_line in (by_item.get(item_code) or []):
            if remaining <= 0:
                break
            avail = _float(bank_line.get("qty"))
            if avail <= 0:
                continue
            take = min(remaining, avail)
            bank_line["qty"] = avail - take
            assigned.append({
                "item_code": item_code,
                "qty": take,
                "idx": int(bank_line.get("idx") or 0),
                "receiving_no": bank_line.get("receiving_no") or "",
                "order_no": bank_line.get("order_no") or "",
            })
            remaining -= take
        if remaining > 0.0001:
            excess.append({
                "item_code": item_code,
                "qty": round(remaining, 4),
            })
    return assigned, excess


def excess_message(excess):
    """Mensaje de alerta cuando una devolucion excede el banco disponible."""
    if not excess:
        return ""
    parts = [
        "{} ({} und.)".format(item.get("item_code"), item.get("qty"))
        for item in excess
    ]
    return (
        "La devolucion excede la cantidad disponible en las lineas de la "
        "factura de referencia: {}".format(", ".join(parts))
    )