import frappe
@frappe.whitelist()
def all():
    
    order()
    invoice()
    receipt()
    execute_truncate("`tabqp_SP_LineErrorSync`")
    frappe.db.commit()
    
@frappe.whitelist()
def order():
    
    execute_truncate("`tabPurchase Order`")
    
    execute_truncate("`tabPurchase Order Item`")
    
    execute_delete("Purchase Order")
    
    frappe.db.commit()

@frappe.whitelist()
def invoice():
    
    execute_truncate("`tabqp_SP_PurchaseInvoice`")

    execute_delete("qp_SP_PurchaseInvoice")
    
    frappe.db.commit()

@frappe.whitelist()
def receipt():
    
    execute_truncate("`tabPurchase Receipt`")
    
    execute_truncate("`tabqp_SP_PurchaseReceiptItem`")
    
    execute_delete("Purchase Receipt")

    execute_truncate("`tabqp_SP_PaymentReceipt`")

    execute_truncate("`tabqp_SP_PaymentReceiptItem`")

    execute_delete("qp_SP_PaymentReceipt")
    
    frappe.db.commit()

def execute_truncate(table):
    
    assertIsAdministrator()
    
    sql = f"TRUNCATE TABLE {table}"
    
    frappe.db.sql(sql)
    
def execute_delete(parenttype):
    
    assertIsAdministrator()
    
    sql = f"delete from tabqp_SP_LineErrorSync where parenttype = '{parenttype}'"
    
    frappe.db.sql(sql)
    
def assertIsAdministrator():
    
    if frappe.session.user != "Administrator":
        
        frappe.throw("No tiene permiso para realizar esta acción")