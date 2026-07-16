"""
fetch_adapter.py
=================
Adaptador para obtener datos desde la API externa (GP middleware).
Implementa el contrato de fetch para las estrategias de sync.
"""

from qp_authorization.use_case.bearer.authorize import send_request


def fetch_invoices(endpoint, param=None):
    return send_request(endpoint, param=param)

