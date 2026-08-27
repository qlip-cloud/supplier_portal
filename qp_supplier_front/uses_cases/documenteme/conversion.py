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


def is_cash_invoice(nvfac_conv):
    """True si la factura es de contado (Nvfac_conv == "1")."""
    return str(nvfac_conv or "") == CONTADO
