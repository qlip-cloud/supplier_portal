import frappe


def execute():

    doctypes = ("Contact", "Address")

    placeholders = ", ".join(["%s"] * len(doctypes))

    groups = frappe.db.sql("""
        SELECT parent, parenttype, link_doctype, link_name, COUNT(*) AS cnt
        FROM `tabDynamic Link`
        WHERE parenttype IN ({placeholders})
        GROUP BY parent, parenttype, link_doctype, link_name
        HAVING cnt > 1
    """.format(placeholders=placeholders), doctypes, as_dict=True)

    for group in groups:

        rows = frappe.db.sql("""
            SELECT name FROM `tabDynamic Link`
            WHERE parent = %s AND parenttype = %s AND link_doctype = %s AND link_name = %s
            ORDER BY idx ASC, name ASC
        """, (group.parent, group.parenttype, group.link_doctype, group.link_name), as_dict=True)

        for row in rows[1:]:

            frappe.db.delete("Dynamic Link", {"name": row.name})

    if groups:

        frappe.db.commit()
