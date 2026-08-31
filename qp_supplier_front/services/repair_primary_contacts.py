# -*- coding: utf-8 -*-
"""
repair_primary_contacts.py (services)
=====================================
Repara el contacto primario de los proveedores.

Contexto del bug:
- El handler de render (www/information/index.py) promovia a primario cualquier
  contacto con telefono al cargar la pagina. Eso cambio el contacto primario
  (el creador) por otro agregado despues, dejando el primario sin `user`.
- Un proveedor sincronizado (GP) no tiene contacto creador: su contacto oficial
  ({index}-{vendorId}) llega con `mobile_no` y `user=mail` pero sin
  `is_primary_contact`.

Reglas:
1. Manual: si el primario no tiene `user` y existe otro contacto con `user`,
   restaurar ese como primario (prioridad: contacto con user == supplier.owner,
   luego el de `creation` mas antigua). Copiar el telefono al primario
   restaurado si no tiene `mobile_no` y algun contacto lo posee.
2. Sync: si el proveedor no tiene ningun primario, designar el contacto oficial
   (con `user`/`creation` mas antigua) como primario.

`dry_run=True` no escribe en la base de datos; solo arma el reporte.
"""

import frappe
from qp_supplier_front.services.get_data import get_dynamic_link


def run(dry_run=True):
    report = []

    suppliers = frappe.get_all("Supplier", pluck="name")

    for supplier_name in suppliers:
        supplier = frappe.get_doc("Supplier", supplier_name)
        contacts = get_dynamic_link(supplier, "Contact")

        entry = _process_supplier(supplier, contacts, dry_run=dry_run)
        report.append(entry)

    return report


def _process_supplier(supplier, contacts, dry_run=True):
    if not contacts:
        return {"supplier": supplier.name, "action": "sin_contactos"}

    entry = {"supplier": supplier.name}

    current_primary = next((c for c in contacts if c.is_primary_contact), None)

    if current_primary and current_primary.user:
        entry["action"] = "ok"
        return entry

    if current_primary:
        candidate = _pick_restore_candidate(contacts, supplier.owner)
        if candidate and candidate.name != current_primary.name:
            entry["action"] = "restaurar_primario"
            entry["candidate"] = candidate.name
            _apply(supplier.name, candidate, contacts, dry_run=dry_run)
            return entry

        entry["action"] = "ok"
        return entry

    candidate = _pick_designate_candidate(contacts)
    entry["action"] = "designar_primario_sync"
    entry["candidate"] = candidate.name if candidate else None
    if candidate:
        _apply(supplier.name, candidate, contacts, dry_run=dry_run)

    return entry


def _pick_restore_candidate(contacts, owner):
    with_user = [c for c in contacts if c.user]
    if not with_user:
        return None

    owner_match = [c for c in with_user if c.user == owner]
    if owner_match:
        return _earliest(owner_match)

    return _earliest(with_user)


def _pick_designate_candidate(contacts):
    with_user = [c for c in contacts if c.user]
    if with_user:
        return _earliest(with_user)
    return _earliest(contacts)


def _earliest(contacts):
    return min(contacts, key=lambda c: c.creation or "")


def _apply(supplier_name, candidate, contacts, dry_run=True):
    if dry_run:
        return

    previous = [c.name for c in contacts if c.is_primary_contact and c.name != candidate.name]

    if not candidate.mobile_no:
        phone_source = next(
            (c.mobile_no for c in contacts if c != candidate and c.mobile_no),
            None
        )
        if phone_source:
            frappe.db.set_value("Contact", candidate.name, "mobile_no", phone_source)

    for contact_name in previous:
        frappe.db.set_value("Contact", contact_name, "is_primary_contact", 0)

    frappe.db.set_value("Contact", candidate.name, "is_primary_contact", 1)
    frappe.db.commit()