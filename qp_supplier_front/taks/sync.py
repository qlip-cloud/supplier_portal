import frappe
from qp_supplier_front.uses_cases.receipts.sync_by_supplier import handler as sync_by_receipts
from qp_supplier_front.uses_cases.sales_invoices.sync_by_supplier import handler as sync_by_invoice
from qp_supplier_front.uses_cases.sales_order.sync_by_supplier import handler as sync_by_order
from qp_supplier_front.uses_cases.item.sync_all import handler as sync_item_all
from qp_supplier_front.uses_cases.supplier.sync_all import handler as sync_supplier_all
from qp_supplier_front.services.utils import add_log
from datetime import datetime
@frappe.whitelist()
def all():
    
    try:
        
        add_log("Inicio Sincronizacion programada all", str(datetime.today()))
    
        sync_item_all()
    
        sync_supplier_all()
    
        sync_purchace_all()
        
        add_log("Fin Sincronizacion programada all", str(datetime.today()))
        
    except Exception as e:
        
        add_log("Error Sincronizacion programada all", str(e),  frappe.get_traceback())
    
    frappe.db.commit()
    
def sync_purchace_all():
    
    suppliers_id = frappe.get_list("Supplier", pluck = "name")
    
    for supplier_id in suppliers_id:
        
        sync_by_receipts(supplier_id)
        sync_by_invoice(supplier_id)
        sync_by_order(supplier_id)