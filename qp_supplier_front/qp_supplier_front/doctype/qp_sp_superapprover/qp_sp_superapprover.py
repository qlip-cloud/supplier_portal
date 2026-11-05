# Copyright (c) 2026, Rafael Licett and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

DOCUMENTEME_APPROVER_ROLES = (
    "Administrador Documenteme",
    "Administrador Sede Documenteme",
)


class qp_SP_SuperApprover(Document):

    def validate(self):
        self.validate_limits()
        self.validate_user()

    def validate_limits(self):
        threshold_amount = _as_float(self.threshold_amount)
        limit_amount = _as_float(self.limit_amount)
        threshold_percentage = _as_float(self.threshold_percentage)
        limit_percentage = _as_float(self.limit_percentage)

        if not (threshold_amount > 0 or threshold_percentage > 0):
            frappe.throw(
                "Configure al menos el umbral por monto o el umbral por porcentaje."
            )
        if limit_amount and limit_amount < threshold_amount:
            frappe.throw(
                "El límite por monto no puede ser menor que el umbral por monto."
            )
        if limit_percentage and limit_percentage < threshold_percentage:
            frappe.throw(
                "El límite por porcentaje no puede ser menor que el umbral por porcentaje."
            )
        if threshold_percentage > 100 or limit_percentage > 100:
            frappe.throw("Los porcentajes no pueden ser mayores a 100.")

    def validate_user(self):
        if not self.user:
            return
        roles = set(frappe.get_roles(self.user))
        if "Administrator" in roles:
            return
        if roles.intersection(DOCUMENTEME_APPROVER_ROLES):
            return
        frappe.throw(
            "El usuario {} no tiene un rol de aprobación de documenteme.".format(
                self.user
            )
        )


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
