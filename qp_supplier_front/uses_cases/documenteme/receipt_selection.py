# -*- coding: utf-8 -*-
"""
receipt_selection.py (documenteme)
==================================
Nucleo puro de la SELECCION MANUAL de recepciones del banco (receipt bank)
para una factura documenteme.

Complementa la aprobacion automatica por banco (receipt_bank.py): el usuario
elige explicitamente que recepciones respaldan la factura, las vincula
(Purchase Receipt.qp_invoice = nvfac_nume) con el boton "aplicar" y, si la
seleccion cubre el subtotal (nvfac_stot) de la factura, dispara el proceso de
aprobacion.

Estados de la seleccion (comparados con epsilon):
- "parcial": suma(marcadas) < nvfac_stot. Aplicar RESERVA los recibos para
  la factura sin iniciar aprobacion; la factura queda NO definitiva y se
  puede desmarcar/ajustar despues.
- "completo": |suma - nvfac_stot| <= epsilon. Aplicar vincula los recibos e
  inicia el proceso de aprobacion (la factura pasa a un estado definitivo).
- "excede": suma > nvfac_stot. Bloqueado: no se puede aplicar hasta
  desmarcar (los recibos son indivisibles).

No importa Frappe: entradas/salidas son dicts/listas planas.
"""

from qp_supplier_front.uses_cases.documenteme.receipt_bank import DEFAULT_EPSILON

# Estados en los que la factura ya no permite aplicar/desmarcar recibos.
DEFINITIVE_STATES = ("BCC", "PA", "PR", "A", "R")


def _to_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def classify_selection(invoice_amount, selected_amount, epsilon=DEFAULT_EPSILON):
    """Clasifica la seleccion respecto al monto de la factura.

    Retorna "parcial", "completo" o "excede". Completo si la suma de los
    recibos seleccionados coincide (epsilon) con el monto de la factura.
    """
    invoice_total = _to_float(invoice_amount)
    selected_total = _to_float(selected_amount)
    if selected_total > invoice_total + epsilon:
        return "excede"
    if abs(selected_total - invoice_total) <= epsilon:
        return "completo"
    return "parcial"


def sum_selected(bank, receipt_names):
    """Suma de montos de los recibos del banco cuyos name estan en receipt_names."""
    by_name = {row.get("name"): row for row in (bank or [])}
    return sum(
        _to_float(by_name.get(name, {}).get("amount"))
        for name in (receipt_names or [])
        if name in by_name
    )


def select_claim_release(claimed_names, checked_names):
    """Calcula que recibos reclamar y que recibos liberar.

    - claimed_names: recibos ya vinculados a ESTA factura (qp_invoice == nume).
    - checked_names: recibos marcados en la UI (los que deben quedar vinculados).

    Retorna (to_claim, to_release):
    - to_claim: marcados que aun no estan vinculados a la factura.
    - to_release: vinculados a la factura que ya no estan marcados.
    """
    claimed = set(claimed_names or [])
    checked = set(checked_names or [])
    return (
        [name for name in (checked_names or []) if name not in claimed],
        [name for name in (claimed_names or []) if name not in checked],
    )


def is_definitive(status):
    return status in DEFINITIVE_STATES


def validate_apply(doc, selected_names, bank, epsilon=DEFAULT_EPSILON):
    """Valida que la seleccion manual pueda aplicarse.

    Retorna (ok, error, classification):
    - ok: False si la factura esta en estado definitivo, no hay recibos
      seleccionados, la seleccion excede el total, o algun recibo seleccionado
      ya no esta disponible (reclamado por otra factura).
    - classification: "parcial"/"completo"/"excede" cuando la validacion se
      puede calcular; None si ok es False por otro motivo.
    """
    status = doc.get("nvfac_esta")
    if is_definitive(status):
        return False, (
            "La factura está en un estado definitivo ({}); no se puede "
            "aplicar ni desmarcar recibos".format(status or "")
        ), None

    invoice_number = doc.get("nvfac_nume")
    by_name = {row.get("name"): row for row in (bank or [])}

    unavailable = []
    for name in (selected_names or []):
        row = by_name.get(name)
        owner = (row or {}).get("qp_invoice")
        if not row or (owner and owner != invoice_number):
            unavailable.append(name)
    if unavailable:
        return False, (
            "Uno o más recibos seleccionados ya no están disponibles "
            "para esta factura: {}".format(", ".join(unavailable))
        ), None

    if not selected_names:
        return False, "Seleccione al menos un recibo para aplicar", None

    classification = classify_selection(
        doc.get("nvfac_stot"), sum_selected(bank, selected_names), epsilon
    )
    if classification == "excede":
        return False, (
            "La selección excede el total de la factura; desmarque recibos "
            "para aplicar"
        ), classification

    return True, "", classification