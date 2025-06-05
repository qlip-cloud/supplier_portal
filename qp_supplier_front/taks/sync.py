import frappe
from qp_supplier_front.uses_cases.receipts.sync_by_supplier import handler_all as sync_by_receipts
from qp_supplier_front.uses_cases.sales_invoices.sync_by_supplier import handler_all as sync_by_invoice
from qp_supplier_front.uses_cases.sales_order.sync_by_supplier import handler_all as sync_by_order
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
            
        sync_by_invoice()
        frappe.db.commit()
        
        sync_by_order()
        frappe.db.commit()
        
        #sync_by_receipts()
        #frappe.db.commit()
        add_log("Fin Sincronizacion programada all", str(datetime.today()))
        
    except Exception as e:
        
        add_log("Error Sincronizacion programada all", str(e),  frappe.get_traceback())
    