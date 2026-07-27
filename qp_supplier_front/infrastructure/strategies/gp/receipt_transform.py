"""
receipt_transform.py (GP)
=========================
Transformacion API GP -> tuplas DB para recibos de pago.
Mapea los campos del endpoint payment_supplier_id/payment_all
al nuevo doctype qp_SP_PaymentReceipt.
Incluye sanitizacion .strip() en campos string.
"""


def _strip(value):
    if isinstance(value, str):
        return value.strip()
    return value


def build_payment_tuple(payment, strategy_name, doc_id, now):
    return (
        doc_id,
        _strip(payment.get("vchrnmbr") or ""),
        _strip(payment.get("vendor") or ""),
        "",
        _strip(payment.get("dinvodof") or ""),
        payment.get("docamnt") or 0,
        "",
        strategy_name,
        "",
        "",
        "",
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_item_tuple(item, doc_id, now):
    return (
        doc_id + ":" + _strip(item.get("aptvchnm") or ""),
        _strip(item.get("aptvchnm") or ""),
        _strip(item.get("seq") or ""),
        item.get("appldamt") or 0,
        _strip(item.get("aptodcnm") or ""),
        doc_id,
        "qp_references",
        "qp_SP_PaymentReceipt",
        now,
        now,
        "Administrator",
        "Administrator"
    )


def build_doc_id(payment):
    return _strip(payment.get("vchrnmbr") or "") + ":" + _strip(payment.get("vendor") or "")


def build_payments(payments_data, strategy_name, now):
    docs = {}
    items = {}
    for payment in payments_data:
        doc_id = build_doc_id(payment)
        docs[doc_id] = build_payment_tuple(
            payment, strategy_name, doc_id, now
        )
        for item in payment.get("reference", []):
            item_id = doc_id + ":" + _strip(item.get("aptvchnm") or "")
            items[item_id] = build_item_tuple(item, doc_id, now)
    return docs, items
