# -*- coding: utf-8 -*-
"""
receipt_claim_adapter.py (infrastructure)
=========================================
Adaptador de seleccion manual del banco de recepciones (documenteme).

Permite vincular (reclamar) y liberar recepciones de compra a una factura
documenteme de forma manual mediante el boton "aplicar":

- get_bank_for_invoice: banco de la OC VISIBLE para una factura (recibos no
  reclamados + los reclamados por ESTA factura). Los reclamados por otras
  facturas NO se incluyen (no son visibles ni seleccionables en otras).
- claim_receipts: UPDATE guardado (qp_invoice IS NULL/vacio) para evitar
  doble reclamo bajo concurrencia. Retorna los nombres que NO pudieron
  reclamarse (tomados por otra factura en paralelo).
- release_receipts: libera recibos reclamados por la factura (qp_invoice=NULL).
- has_claimed_receipts / claimed_invoice_numbers: soporte para que los flujos
  automaticos (promote, auto_approve, auto_assign, auto_reject) excluyan las
  facturas con seleccion manual en curso.

Reglas:
- Frappe se importa lazy (dentro de cada funcion) para poder importar el
  modulo sin Frappe instalado.
- Cada funcion acepta el framework como parametro de inyeccion OPCIONAL.
"""


def get_bank_for_invoice(purchase_order_number, invoice_number,
                         frappe_module=None):
    """Banco de recepciones disponible para la seleccion manual de una factura.

    Retorna filas {name, amount, date, qp_invoice, claimed_by_me, selectable}
    con los recibos de la OC que ESTA factura puede ver/controlar.
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not purchase_order_number or not invoice_number:
        return []

    receipts = frappe_module.get_all(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order_number},
        fields=["name", "total", "posting_date", "qp_invoice"],
    )

    rows = []
    for receipt in receipts:
        owner = receipt.get("qp_invoice")
        if owner and owner != invoice_number:
            continue
        rows.append({
            "name": receipt.get("name"),
            "amount": receipt.get("total") or 0,
            "date": receipt.get("posting_date"),
            "qp_invoice": owner,
            "claimed_by_me": owner == invoice_number,
            "selectable": True,
        })
    return rows


def claim_receipts(doc, receipt_names, frappe_module=None):
    """Vincula recepciones a la factura (qp_invoice = nvfac_nume).

    UPDATE guardado: solo vincula recepciones cuyo qp_invoice sigue vacio.
    Retorna la lista de nombres que NO pudieron reclamarse (una factura
    concurrente se los llevo entre la validacion y el UPDATE).
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not receipt_names:
        return []

    invoice_number = doc.get("nvfac_nume")
    if not invoice_number:
        return list(receipt_names)

    names = list(receipt_names)
    placeholders = ", ".join(["%s"] * len(names))
    frappe_module.db.sql(
        "UPDATE `tabPurchase Receipt` SET qp_invoice = %s "
        "WHERE name IN ({}) AND (qp_invoice IS NULL OR qp_invoice = '')".format(
            placeholders
        ),
        [invoice_number] + names,
    )

    claimed = set(frappe_module.get_all(
        "Purchase Receipt",
        filters={"name": ["in", names], "qp_invoice": invoice_number},
        pluck="name",
    ))
    return [name for name in names if name not in claimed]


def release_receipts(doc, receipt_names, frappe_module=None):
    """Libera recepciones reclamadas por ESTA factura (qp_invoice = NULL).

    Solo afecta recibos cuyo qp_invoice coincide con la factura: nunca
    libera un recibo reclamado por otra factura.
    """
    if frappe_module is None:
        import frappe as frappe_module

    if not receipt_names:
        return

    invoice_number = doc.get("nvfac_nume")
    if not invoice_number:
        return

    names = list(receipt_names)
    placeholders = ", ".join(["%s"] * len(names))
    frappe_module.db.sql(
        "UPDATE `tabPurchase Receipt` SET qp_invoice = NULL "
        "WHERE name IN ({}) AND qp_invoice = %s".format(placeholders),
        names + [invoice_number],
    )


def has_claimed_receipts(invoice_number, frappe_module=None):
    """True si la factura tiene al menos un recibo reclamado manualmente."""
    if not invoice_number:
        return False
    if frappe_module is None:
        import frappe as frappe_module
    rows = frappe_module.get_all(
        "Purchase Receipt",
        filters={"qp_invoice": invoice_number},
        pluck="name",
        limit=1,
    )
    return bool(rows)


def claimed_invoice_numbers(frappe_module=None):
    """Conjunto de facturas con algun recibo reclamado (para gates automaticos)."""
    if frappe_module is None:
        import frappe as frappe_module
    values = frappe_module.get_all(
        "Purchase Receipt",
        filters={"qp_invoice": ["is", "set"]},
        pluck="qp_invoice",
    )
    return set(value for value in values if value)