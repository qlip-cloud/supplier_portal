def set_name(doc, method):
    if not doc.is_new():
        return

    if doc.order_confirmation_no:
        doc.name = doc.order_confirmation_no
        doc.qp_order_confirmation_no = doc.order_confirmation_no
        doc.qp_order_id = doc.order_confirmation_no
        doc.qp_create_date = doc.transaction_date
        doc.flags.name_set = True

    _set_item_rate(doc)


def _set_item_rate(doc):
    for item in doc.get("items") or []:
        if not item.rate and item.qp_unit_cost:
            item.rate = item.qp_unit_cost
