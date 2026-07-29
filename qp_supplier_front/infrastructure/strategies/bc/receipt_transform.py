"""
receipt_transform.py (BC)
==========================
Transformacion API BC -> tuplas DB para recibos de pago.
Agrupa las lineas del API por Document_No_Pago: cada grupo genera
un registro padre (qp_SP_PaymentReceipt) y N registros hijos
(qp_SP_PaymentReceiptItem) con los datos de cada factura asociada.
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
        _strip(payment.get("Document_Type_Pago") or ""),
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_item_tuple(line, doc_id, now):
    return (
        doc_id + ":" + _strip(line.get("Document_No_Factura") or ""),
        _strip(line.get("Document_No_Factura") or ""),
        str(line.get("AuxiliaryIndex2") or ""),
        line.get("Amount_Factura") or 0,
        _strip(line.get("External_Document_No_") or ""),
        doc_id,
        "qp_references",
        "qp_SP_PaymentReceipt",
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_doc_id(payment):
    return _strip(payment.get("Document_No_Pago") or "") + ":" + _strip(payment.get("Vendor_No_") or "")


def build_payments(payments_data, strategy_name, now):
    groups = {}
    for payment in payments_data:
        key = _strip(payment.get("Document_No_Pago") or "")
        groups.setdefault(key, []).append(payment)

    docs = {}
    items = {}
    for doc_no, lines in groups.items():
        first = lines[0]
        doc_id = build_doc_id(first)
        docs[doc_id] = build_payment_tuple(first, strategy_name, doc_id, now)
        for line in lines:
            item_id = doc_id + ":" + _strip(line.get("Document_No_Factura") or "")
            items[item_id] = build_item_tuple(line, doc_id, now)
    return docs, items
