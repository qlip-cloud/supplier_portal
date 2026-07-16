"""
fetch_oauth_adapter.py
=======================
Adaptador OAuth2 para Business Central (BC).
Usa qp_md_Endpoint / qp_md_Setup / qp_md_Enviroment (OData v4)
y maneja paginacion via @odata.nextLink.
Misma firma (endpoint, param) que fetch_adapter.py para DI.
"""

from qp_authorization.use_case.oauth2.authorize import get_token


def fetch_invoices(endpoint, param=None):
    import frappe
    import requests as http_requests
    import json

    endpoint_doc = frappe.get_doc("qp_md_Endpoint", endpoint)
    setup = frappe.get_doc("qp_md_Setup", endpoint_doc.setup)
    environment = frappe.get_doc("qp_md_Enviroment", setup.enviroment)

    token = get_token(environment.name)
    url = environment.get_url(endpoint_doc)
    url += "&$top=10" if "?" in url else "?$top=10"
    if param:
        url += "/" + str(param)

    headers = {
        'Authorization': 'Bearer {}'.format(token)
    }

    maxpagesize = setup.invoices_group
    if maxpagesize and maxpagesize > 0:
        headers['Prefer'] = 'odata.maxpagesize={}'.format(maxpagesize)

    result = {"value": []}
    _fetch_pages(url, headers, result)
    return result


def _fetch_pages(url, headers, result):
    import frappe
    import requests as http_requests
    import json

    response = http_requests.get(url, headers=headers)

    if response.status_code != 200:
        frappe.throw(
            "Error en solicitud BC: {} status {}".format(
                response.reason, response.status_code
            )
        )

    data = json.loads(response.text)

    if "error" in data:
        frappe.throw(data["error"])

    result["value"] += data.get("value", [])

    next_link = data.get("@odata.nextLink")
    if next_link:
        _fetch_pages(next_link, headers, result)
