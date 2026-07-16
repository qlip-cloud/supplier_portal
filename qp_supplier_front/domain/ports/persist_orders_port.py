"""
persist_orders_port.py
======================
Contrato para persistir facturas/proveedores sincronizados.

Cada estrategia (GP, BC, futuro) debe implementar las siguientes
funciones para persistir los datos transformados:

    insert_invoices(docs, now)
        docs: { doc_id: (name, invoice_id, status, create_date,
                         registration_date, currency, subtotal, tax,
                         total, supplier, detail, qp_sync_flow,
                         creation, modified, modified_by, owner) }
        now: timestamp string para creation/modified

    insert_errors(errors, now)
        errors: { error_id: (name, line, code, error, parent,
                             parentfield, parenttype, creation,
                             modified, modified_by, owner) }
        now: timestamp string para creation/modified

Funciones documentadas como referencia del contrato.
No hay clase abstracta por compatibilidad Python 3.6.
"""

