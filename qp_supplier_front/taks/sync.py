import frappe
from qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier import sync_incremental as sync_receipt_recent
from qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier import sync_incremental as sync_invoice_recent
from qp_supplier_front.uses_cases.item.sync_all import handler as sync_item_all
from qp_supplier_front.uses_cases.supplier.sync_all import handler as sync_supplier_all
from qp_supplier_front.services.utils import add_log
from datetime import datetime
@frappe.whitelist()
def all():
    
    try:
        
        add_log("Inicio Sincronizacion programada all", str(datetime.today()))
    
        sync_item_all()
        frappe.db.commit()
        sync_supplier_all()
        frappe.db.commit()
        
        add_log("Fin Sincronizacion programada all", str(datetime.today()))
        
    except Exception as e:
        
        add_log("Error Sincronizacion programada all", str(e),  frappe.get_traceback())


def scheduled_sync_recent():
    """
    Sincronizacion incremental cada 5 minutos (solo BC).
    Sincroniza el dia actual en ventana global (sin filtro de proveedores)
    para facturas y recibos.
    Se omite si hay una sincronizacion manual en curso (lock activo).
    """
    try:
        result = sync_receipt_recent()
        if result.get("skipped"):
            add_log("Sync 5min omitido (lock activo): recibos", str(datetime.today()))
        frappe.db.commit()

        result = sync_invoice_recent()
        if result.get("skipped"):
            add_log("Sync 5min omitido (lock activo): facturas", str(datetime.today()))
        frappe.db.commit()

        add_log("Fin Sincronizacion incremental 5 min", str(datetime.today()))
    except Exception as e:
        add_log("Error Sincronizacion incremental 5 min", str(e), frappe.get_traceback())
