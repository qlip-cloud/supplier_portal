import frappe

DOCTYPE = "Purchase Receipt"
ALIAS_FIELD = "supplier_oc"
CANONICAL_FIELD = "qp_supplier_oc"


def execute():
    """Sincroniza la OC de los recibos entre el campo externo y el canonical.

    La integracion externa (BC) puede haber guardado la OC en `supplier_oc`,
    mientras documenteme la lee de `qp_supplier_oc`. Re-sincronizar facturas no
    toca los recibos, por eso poblamos los recibos existentes una sola vez.

    Solo rellena valores vacios (idempotente, no pisa datos existentes).
    """
    if not frappe.db.has_column(DOCTYPE, ALIAS_FIELD):
        return
    if not frappe.db.has_column(DOCTYPE, CANONICAL_FIELD):
        return

    frappe.db.sql(
        """UPDATE `tabPurchase Receipt`
        SET qp_supplier_oc = supplier_oc
        WHERE IFNULL(qp_supplier_oc, '') = ''
          AND IFNULL(supplier_oc, '') <> ''"""
    )

    frappe.db.sql(
        """UPDATE `tabPurchase Receipt`
        SET supplier_oc = qp_supplier_oc
        WHERE IFNULL(supplier_oc, '') = ''
          AND IFNULL(qp_supplier_oc, '') <> ''"""
    )

    frappe.db.commit()
