"""
receipt_transform.py (BC)
==========================
Transformacion API BC -> tuplas DB para recibos de pago.
BC no trae items (child records), solo datos de cabecera.
Incluye sanitizacion .strip() en campos string.
"""


def _strip(value):
    if isinstance(value, str):
        return value.strip()
    return value


def build_payment_tuple(payment, strategy_name, doc_id, now):
    return (
        doc_id,
        _strip(payment.get("Document_No_Pago") or ""),
        _strip(payment.get("Vendor_No_") or ""),
        _strip(payment.get("Vendor_Name") or ""),
        payment.get("Posting_Date"),
        payment.get("Amount_Pago") or 0,
        _strip(payment.get("Description") or ""),
        strategy_name,
        _strip(payment.get("External_Document_No_") or ""),
        _strip(payment.get("Document_Type_Pago") or ""),
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_doc_id(payment):
    return _strip(payment.get("Document_No_Pago") or "") + ":" + _strip(payment.get("Vendor_No_") or "")


def build_payments(payments_data, strategy_name, now):
    docs = {}
    for payment in payments_data:
        doc_id = build_doc_id(payment)
        docs[doc_id] = build_payment_tuple(
            payment, strategy_name, doc_id, now
        )
    return docs, {}
