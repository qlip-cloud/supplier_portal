def set_name(doc, method):
    import frappe
    if not doc.qp_orden_externa:
        frappe.throw("El campo 'Orden Externa' es obligatorio para crear una Orden de Venta")
    doc.name = doc.qp_orden_externa
