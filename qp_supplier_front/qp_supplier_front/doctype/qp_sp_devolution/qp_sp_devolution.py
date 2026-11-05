# -*- coding: utf-8 -*-
"""
qp_sp_devolution.py
===================
DocType que registra el consumo del banco de devoluciones de una NC tipo 5:
cuanta cantidad de cada linea de recepcion/OC de la factura de compra
referenciada ya fue devuelta (cantidad utilizada por la nota de credito).
"""

from frappe.model.document import Document


class QpSpDevolution(Document):
    pass