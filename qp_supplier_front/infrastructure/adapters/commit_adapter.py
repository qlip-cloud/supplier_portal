"""
commit_adapter.py
==================
Adaptadores para commit y logging de errores.
"""

import frappe


def commit():
    frappe.db.commit()


def rollback():
    frappe.db.rollback()


def log_error(message, title):
    frappe.log_error(message=message, title=title)

