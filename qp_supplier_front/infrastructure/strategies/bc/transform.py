"""
transform.py (BC)
==================
Transformacion API BC -> tuplas DB.
Los valores que el cliente decida manejar (Purchase_LCY_49235=0,
Amount_LCY negativo) se persisten tal cual llegan.
"""


def build_invoice_tuple(invoice, strategy_name, doc_id, now):
    lhi_iva = invoice.get("LHCIva") or 0
    lhi_rete_fuente = invoice.get("LHCReteFuente") or 0
    lhi_rete_iva = invoice.get("LHCReteIva") or 0
    lhi_rete_ica = invoice.get("LHCReteIca") or 0
    amount_lcy = invoice.get("Amount_LCY") or 0
    currency = invoice.get("Currency_Code")
    if not currency:
        currency = "COP"
    remaining_amt_lcy = invoice.get("Remaining_Amt_LCY") or 0

    tax = lhi_iva + lhi_rete_fuente + lhi_rete_iva + lhi_rete_ica
    total = amount_lcy - (lhi_rete_fuente + lhi_rete_iva + lhi_rete_ica)
    status = "Pagado" if remaining_amt_lcy == 0 else "Abierto"

    return (
        doc_id,
        invoice.get("Document_No"),
        status,
        invoice.get("Posting_Date"),
        invoice.get("Document_Date"),
        currency,
        invoice.get("Purchase_LCY_49235") or 0,
        tax,
        total,
        invoice.get("Vendor_No"),
        invoice.get("Description") or "",
        invoice.get("LHCOrdenCompra") or "",
        strategy_name,
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_doc_id(invoice):
    return str(invoice.get("Entry_No")) + ":" + invoice.get("Vendor_No")


def build_invoices(invoices_data, strategy_name, now):
    docs = {}
    for invoice in invoices_data:
        if invoice.get("Document_Type") != "Invoice":
            continue
        doc_id = build_doc_id(invoice)
        docs[doc_id] = build_invoice_tuple(
            invoice, strategy_name, doc_id, now
        )
    return docs

