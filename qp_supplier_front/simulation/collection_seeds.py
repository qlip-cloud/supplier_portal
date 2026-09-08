# -*- coding: utf-8 -*-
"""
collection_seeds.py (simulation)
================================
Seeds de datos de referencia (Purchase Order, Purchase Order Item, Purchase
Receipt, Supplier, sede) y de escenario (cuentas de cobro + facturas) para el
modo simulador del flujo de cuentas de cobro.

Pueblan el MemoryStore de la sesion para que crear/evaluar/aprobar/rechazar
tengan input real sin tocar la base de datos. Los seeds son idempotentes:
re-ejecutarlos sobre un store ya sembrado es un no-op (los mutados por el
flujo, p. ej. qp_invoice de recibos, no se pisan).
"""

from qp_supplier_front.simulation.seeds import (
    SIM_NIT,
    _insert_if_missing,
    seed_master_setup,
    seed_purchase_receipt,
    seed_purchase_receipt_item,
    seed_reject_rule,
    seed_sede,
    seed_supplier,
)

PURCHASE_ORDER = "qp_SP_PurchaseOrder"
PURCHASE_ORDER_ITEM = "qp_SP_PurchaseOrderItem"
COLLECTION_ACCOUNT = "qp_SP_CollectionAccounts"
PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
NOTIFICATIONS = "qp_SP_PurchaseInvoiceNotification"


def seed_collection_po(store, name, supplier, grand_total,
                       currency="COP", headquarter="HQ01"):
    _insert_if_missing(store, PURCHASE_ORDER, {
        "name": name,
        "supplier": supplier,
        "grand_total": grand_total,
        "currency": currency,
        "qp_headquarter": headquarter,
    })


def seed_collection_po_item(store, parent, item_code, qty, rate, idx=1,
                            uom="UND"):
    _insert_if_missing(store, PURCHASE_ORDER_ITEM, {
        "name": "{}:{}".format(parent, item_code),
        "parent": parent,
        "parenttype": "Purchase Order",
        "item_code": item_code,
        "uom": uom,
        "qty": qty,
        "rate": rate,
        "idx": idx,
    })


def seed_collection_account(store, name, purchase_order, amount_payable,
                            total_due, available_amount, supplier,
                            creation_date, status="Borrador"):
    _insert_if_missing(store, COLLECTION_ACCOUNT, {
        "name": name,
        "supplier_id": supplier,
        "supplier": supplier,
        "purchase_order": purchase_order,
        "total_due": total_due,
        "available_amount": available_amount,
        "amount_payable": amount_payable,
        "observations": "",
        "docs": "",
        "status": status,
        "creation_date": creation_date,
    }, name=name)


def seed_collection_purchase_invoice(store, name, collection_account,
                                     purchase_order, supplier, total,
                                     qp_status, creation_date,
                                     error_message=None):
    _insert_if_missing(store, PURCHASE_INVOICE, {
        "name": name,
        "invoice_id": "",
        "status": "Abierto",
        "qp_status": qp_status,
        "qp_sync_flow": "COLLECTION",
        "supplier": supplier,
        "purchase_order_id": purchase_order,
        "nvpro_ndoc": supplier,
        "nvfac_fech": creation_date,
        "nvfac_nume": name,
        "nvfac_cufe": "",
        "nvfac_conv": "1",
        "currency": "COP",
        "subtotal": total,
        "tax": 0,
        "total": total,
        "collection_account": collection_account,
        "qp_error_message": error_message or "",
        "registration_date": creation_date,
    }, name=name)


def seed_notification(store, parent, message, notification_type="Alerta",
                      status="Abierta"):
    _insert_if_missing(store, NOTIFICATIONS, {
        "parent": parent,
        "parenttype": PURCHASE_INVOICE,
        "parentfield": "notifications",
        "notification_date": "2026-09-02 10:00:00",
        "notification_type": notification_type,
        "notification_message": message,
        "status": status,
    })


def seed_collection_scenario(store):
    """Escenario completo del modo simulador de cuentas de cobro.

    Las facturas se tratan como CONTADO (nvfac_conv=1): NO exigen OC/recibos
    salvo por la regla de rechazo activa. El MasterSetup apunta a la regla
    "no_receipt":

    - PO-CA-0001 con recibos -> CA-SIM-0001 -> factura V (aprobable).
    - PO-CA-0002 con un recibo -> CA-SIM-0002 -> factura V.
    - PO-CA-0003 SIN recibos -> CA-SIM-0003 -> factura E (viola la regla
      no_receipt) con notificacion ErrorUrgente.
    """
    seed_supplier(store, SIM_NIT)
    seed_sede(store, "HQ01")
    seed_reject_rule(store, "RULE-NO-RECEIPT", "no_receipt",
                     motive="Rechazo: sin recibo de compra")
    seed_master_setup(
        store,
        collection_invoices_simulation=1,
        auto_reject="RULE-NO-RECEIPT",
    )

    seed_collection_po(store, "PO-CA-0001", SIM_NIT, 1000000)
    seed_collection_po_item(store, "PO-CA-0001", "ITEM-0001", 1, 600000, idx=1)
    seed_collection_po_item(store, "PO-CA-0001", "ITEM-0002", 2, 200000, idx=2)

    seed_purchase_receipt(store, "REC-CA1-1", "PO-CA-0001", 200000,
                          posting_date="2026-08-20")
    seed_purchase_receipt(store, "REC-CA1-2", "PO-CA-0001", 400000,
                          posting_date="2026-08-21")
    seed_purchase_receipt(store, "REC-CA1-3", "PO-CA-0001", 400000,
                          posting_date="2026-08-22")
    seed_purchase_receipt_item(store, "REC-CA1-1", "ITEM-REC-1", 1, 200000)
    seed_purchase_receipt_item(store, "REC-CA1-2", "ITEM-REC-2", 1, 400000)
    seed_purchase_receipt_item(store, "REC-CA1-3", "ITEM-REC-3", 1, 400000)

    seed_collection_po(store, "PO-CA-0002", SIM_NIT, 500000)
    seed_collection_po_item(store, "PO-CA-0002", "ITEM-0003", 1, 500000, idx=1)

    seed_purchase_receipt(store, "REC-CA2-1", "PO-CA-0002", 100000,
                          posting_date="2026-08-25")
    seed_purchase_receipt_item(store, "REC-CA2-1", "ITEM-REC-4", 1, 100000)

    seed_collection_po(store, "PO-CA-0003", SIM_NIT, 100000)
    seed_collection_po_item(store, "PO-CA-0003", "ITEM-0004", 1, 100000, idx=1)

    seed_collection_account(
        store, "CA-SIM-0001", "PO-CA-0001", 600000, 1000000, 1000000,
        SIM_NIT, "2026-09-01",
    )
    seed_collection_account(
        store, "CA-SIM-0002", "PO-CA-0002", 500000, 500000, 500000,
        SIM_NIT, "2026-09-02",
    )
    seed_collection_account(
        store, "CA-SIM-0003", "PO-CA-0003", 100000, 100000, 100000,
        SIM_NIT, "2026-09-03",
    )

    seed_collection_purchase_invoice(
        store, "PI-SIM-0001", "CA-SIM-0001", "PO-CA-0001", SIM_NIT, 600000,
        "V", "2026-09-01",
    )
    seed_collection_purchase_invoice(
        store, "PI-SIM-0002", "CA-SIM-0002", "PO-CA-0002", SIM_NIT, 500000,
        "V", "2026-09-02",
    )
    seed_collection_purchase_invoice(
        store, "PI-SIM-0003", "CA-SIM-0003", "PO-CA-0003", SIM_NIT, 100000,
        "E", "2026-09-03",
        error_message=(
            "La factura de contado no cumple la regla de rechazo configurada "
            "(no_receipt), por lo que no se aprueba automáticamente y debe "
            "asignarse"
        ),
    )
    seed_notification(
        store, "PI-SIM-0003",
        "La factura de contado no cumple la regla de rechazo configurada "
        "(no_receipt), por lo que no se aprueba automáticamente y debe asignarse",
        notification_type="ErrorUrgente",
    )