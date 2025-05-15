import frappe
from qp_supplier_front.uses_cases.receipts.sync_by_supplier import handler as sync_by_receipts
from qp_supplier_front.uses_cases.sales_invoices.sync_by_supplier import handler as sync_by_invoice
from qp_supplier_front.uses_cases.sales_order.sync_by_supplier import handler as sync_by_order

@frappe.whitelist()
def all():
    
    
    
    suppliers_id = frappe.get_list("Supplier", pluck = "name")
    
    for supplier_id in suppliers_id:
        
        #sync_by_receipts(supplier_id)
        sync_by_invoice(supplier_id)
        #sync_by_order(supplier_id)