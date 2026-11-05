def on_receipt_created(doc, method=None):
    import frappe

    try:
        if _is_running_in_bulk(frappe):
            return
        order = (doc.get("qp_supplier_oc") or "").strip()
        if not order:
            return
        if not _auto_approve_enabled():
            return
        doc_names = _invoice_names_for_order(order)
        if not doc_names:
            return
        _enqueue_auto_approve(frappe, doc_names)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "documenteme receipt auto approve",
        )


def _is_running_in_bulk(frappe):
    flags = frappe.flags
    return bool(
        getattr(flags, "in_import", False)
        or getattr(flags, "in_migrate", False)
        or getattr(flags, "in_patch", False)
    )


def _auto_approve_enabled():
    from qp_supplier_front.resources.documenteme.auto_approve import (
        is_auto_approve_enabled,
    )

    return is_auto_approve_enabled()


def _invoice_names_for_order(order):
    import frappe
    from qp_supplier_front.uses_cases.documenteme.purchase_orders import (
        parse_purchase_orders,
    )

    rows = frappe.get_all(
        "qp_SP_DocumentDetail",
        filters={
            "nvfac_esta": ["in", ["E", "T", "V"]],
            "nvfac_ueve": ["is", "not set"],
            "nvfac_orde": ["like", "%{0}%".format(order)],
        },
        fields=["name", "nvfac_orde"],
    )
    return [
        row.get("name")
        for row in (rows or [])
        if order in parse_purchase_orders(row.get("nvfac_orde"))
    ]


def _enqueue_auto_approve(frappe, doc_names):
    frappe.enqueue(
        "qp_supplier_front.resources.documenteme.auto_approve.auto_approve_now",
        queue="long",
        timeout=14400,
        job_name="auto approve receipt",
        enqueue_after_commit=True,
        doc_names=list(doc_names),
    )
