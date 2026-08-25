"""
documenteme_http_adapter.py
===========================
Adaptadores de infraestructura compartidos por el modulo documenteme.

Consolida helpers duplicados que vivian en resources/documenteme
(auto_reject, auto_approve_confirmation, auto_assign, _approve_base y
_reject_base):

- raw_http: envio HTTP del evento hacia documenteme.
- get_event_endpoint: endpoint autenticado del evento de documenteme.
- get_company_tax_id: NIT de la compania del usuario actual.
- get_receipt_total: suma del total de Purchase Receipt por orden de compra.

Reglas:
- Todos los frameworks (frappe, requests, json, qp_authorization) se
  importan de forma perezosa DENTRO de cada funcion, de modo que este
  modulo pueda importarse sin Frappe instalado (lazy imports).
- Cada funcion acepta el framework (frappe/requests) como parametro de
  inyeccion OPCIONAL. Cuando se omite, hace un import perezoso. Esto
  permite a los modulos consumidores inyectar la referencia de su propio
  namespace de modulo (necesario para que los tests que parchean el
  atributo del modulo sigan funcionando).
"""


def raw_http(payload, url, headers, method, requests_module=None):
    """Envia un evento a documenteme y devuelve (respuesta, status_code).

    Ante cualquier excepcion de red devuelve ({"errorInterno": str(error)}, 500).
    """
    import json

    if requests_module is None:
        import requests as requests_module

    data = json.dumps(payload)
    try:
        resp = requests_module.request(method, url, headers=headers, data=data)
        return json.loads(resp.text), resp.status_code
    except Exception as error:
        return {"errorInterno": str(error)}, 500


def get_event_endpoint():
    """Endpoint autenticado del evento de documenteme: (url, headers, method)."""
    from qp_authorization.use_case.basic.authorize import (
        get_enviroment,
        get_headers,
    )
    from qp_supplier_front.constant.endpoint import DOCUMENTEME_EVENT_DOCUMENT

    environment, endpoint, _ = get_enviroment(DOCUMENTEME_EVENT_DOCUMENT)
    url = environment.get_url(endpoint.url)
    return url, get_headers(environment), endpoint.method


def get_company_tax_id(frappe_module=None):
    """NIT de la compania configurada por defecto para el usuario actual."""
    if frappe_module is None:
        import frappe as frappe_module

    company = frappe_module.get_doc(
        "Company", frappe_module.defaults.get_user_default("company")
    )
    return company.tax_id


def get_receipt_total(purchase_order_number, frappe_module=None):
    """Suma del total de Purchase Receipt asociados a una orden de compra.

    Devuelve None si falta la OC o si no hay recibos. La suma ignora
    recibos sin total (total None -> 0).
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not purchase_order_number:
        return None

    receipts = frappe_module.get_all(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order_number},
        fields=["total"],
    )

    if not receipts:
        return None

    return sum(receipt.get("total") or 0 for receipt in receipts)
