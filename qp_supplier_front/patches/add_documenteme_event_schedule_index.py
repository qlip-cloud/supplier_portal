"""
add_documenteme_event_schedule_index.py
=======================================
Prepara qp_SP_DocumentDetail para el dispatcher de eventos documenteme
(event_dispatch.dispatch_pending_events, cron cada minuto):

  - Rellena qp_event_next_at para documentos en proceso (PR/PA) que quedaron
    sin el campo (documentos legados): se marcan como vencidos para que el
    dispatcher los retome de inmediato y drene el backlog.
  - Normaliza qp_reject_retry_enabled a 1 cuando es NULL.
  - Crea el indice compuesto (nvfac_esta, qp_event_next_at) para que la
    consulta por minuto sea un range scan acotado y no un full table scan.

Idempotente.
"""

import frappe

DOCTYPE = "qp_SP_DocumentDetail"
INDEX_FIELDS = ["nvfac_esta", "qp_event_next_at"]


def execute():
    if not frappe.db.table_exists(DOCTYPE):
        return

    frappe.db.sql(
        """
        UPDATE `tabqp_SP_DocumentDetail`
        SET qp_event_next_at = NOW()
        WHERE nvfac_esta IN ('PR', 'PA')
          AND qp_event_next_at IS NULL
        """
    )
    frappe.db.sql(
        """
        UPDATE `tabqp_SP_DocumentDetail`
        SET qp_reject_retry_enabled = 1
        WHERE qp_reject_retry_enabled IS NULL
        """
    )
    frappe.db.add_index(DOCTYPE, INDEX_FIELDS)
    frappe.db.commit()
