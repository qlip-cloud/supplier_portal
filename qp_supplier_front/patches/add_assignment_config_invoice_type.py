# -*- coding: utf-8 -*-
"""add_assignment_config_invoice_type.py

Backfill del campo `invoice_type` en `qp_SP_AssignmentConfig`.

Antes de este cambio la fila catch-all (oc_type y headquarter vacios) solo se
usaba para las facturas de CONTADO sin OC. El nuevo flujo de credito sin OC
necesita destinatarios propios, asi que:

- Las filas catch-all existentes pasan a `Contado` (su alcance efectivo hoy).
- Cualquier fila restante con el campo vacio queda en `Todos` (sin cambio de
  comportamiento).
"""

import frappe


DOCTYPE = "qp_SP_AssignmentConfig"

CATCH_ALL_UPDATE = """
UPDATE `tabqp_SP_AssignmentConfig`
SET invoice_type = 'Contado'
WHERE (oc_type IS NULL OR oc_type = '')
  AND (headquarter IS NULL OR headquarter = '')
  AND (invoice_type IS NULL OR invoice_type = '' OR invoice_type = 'Todos')
"""


DEFAULT_UPDATE = """
UPDATE `tabqp_SP_AssignmentConfig`
SET invoice_type = 'Todos'
WHERE invoice_type IS NULL OR invoice_type = ''
"""


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return

    # Los patches corren antes de sync_all, por lo que `invoice_type` aun no
    # existe. Forzamos el sync del doctype para crearla antes del backfill.
    frappe.reload_doc("qp_supplier_front", "doctype", DOCTYPE, force=True)

    frappe.db.sql(DEFAULT_UPDATE)
    frappe.db.sql(CATCH_ALL_UPDATE)
    frappe.db.commit()
