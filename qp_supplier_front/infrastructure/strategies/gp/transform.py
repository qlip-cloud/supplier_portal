"""
transform.py (GP)
==================
Funciones puras de transformacion API -> tuplas DB.
Extraidas de get_doc_base en sales_invoices/sync_by_supplier.py.
Sin cambios en la logica de mapeo.
"""


def build_invoice_tuple(invoice, strategy_name, doc_id, now):
    return (
        doc_id,
        invoice.get("invoiceId"),
        invoice.get("status"),
        invoice.get("createdate"),
        invoice.get("registrationDate"),
        invoice.get("currency"),
        invoice.get("subTotal"),
        invoice.get("tax"),
        invoice.get("total"),
        invoice.get("vendor"),
        invoice.get("detail"),
        "",
        strategy_name,
        now,
        now,
        "Administrator",
        "Administrator"
    )


def filter_invoices(invoices_data, max_length=140):
    return invoices_data, []


def build_doc_id(invoice):
    return invoice.get("invoiceId") + ":" + invoice.get("vendor")


def build_invoices(invoices_data, strategy_name, now):
    docs = {}
    for invoice in invoices_data:
        doc_id = build_doc_id(invoice)
        docs[doc_id] = build_invoice_tuple(
            invoice, strategy_name, doc_id, now
        )
    return docs

