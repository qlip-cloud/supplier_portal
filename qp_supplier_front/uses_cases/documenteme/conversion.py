# -*- coding: utf-8 -*-
"""
conversion.py (documenteme)
===========================
Helpers puros para diferenciar el tipo de conversion de una factura
documenteme segun el campo Nvfac_conv:

- "2": Credito (comportamiento actual: notifica aprobacion/rechazo).
- "1": Contado (las facturas se crean/rechazan en BC pero NO se notifica
  ningun evento a documenteme).

No importa Frappe: funciones puras y testables en aislamiento.
"""

CONTADO = "1"

CREDITO = "2"

# Valor de qp_SP_DocumentDetail.nvtip_docu para Nota Credito. La etiqueta
# mostrada al usuario en el front es "NC" (templates .../list.html mapea
# "C" -> "NC").
NC_TIPO_DOCU = "C"


def is_cash_invoice(nvfac_conv):
    """True si la factura es de contado (Nvfac_conv == "1")."""
    return str(nvfac_conv or "") == CONTADO


def is_credit_note(nvtip_docu):
    """True si el documento es una Nota Credito (nvtip_docu == "C").

    Las notas credito se envian a GP con tipoFacturaDoc=4 y SIN productos,
    sin restricciones ni validaciones: siempre se aprueban.
    """
    return str(nvtip_docu or "") == NC_TIPO_DOCU
