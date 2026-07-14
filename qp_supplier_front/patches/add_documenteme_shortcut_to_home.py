import frappe


def execute():
    parent = "Home"
    link_to = "documenteme"

    existing = frappe.db.sql("""SELECT name FROM `tabWorkspace Shortcut`
        WHERE parent=%s AND parenttype='Workspace' AND type='Page' AND link_to=%s""",
        (parent, link_to))
    if existing:
        return

    max_idx = frappe.db.sql("""SELECT IFNULL(MAX(idx), 0) FROM `tabWorkspace Shortcut`
        WHERE parent=%s AND parenttype='Workspace'""", parent)[0][0]

    frappe.db.sql("""INSERT INTO `tabWorkspace Shortcut`
        (name, creation, modified, modified_by, owner, docstatus, parent,
         parenttype, parentfield, idx, type, link_to, label, icon, color, format)
        VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, %s,
         'Workspace', 'shortcuts', %s, 'Page', %s, 'Facturas de venta',
         'invoice', '#4F46E5', 'Documenteme')""",
        (frappe.generate_hash("", 10), parent, max_idx + 1, link_to))

    frappe.db.commit()
