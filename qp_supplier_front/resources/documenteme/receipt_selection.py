# -*- coding: utf-8 -*-
"""
receipt_selection.py (documenteme) — infraestructura
====================================================
Seleccion manual del banco de recepciones para una factura documenteme.

- get_bank(doc_name): banco visible para la factura (recibos no reclamados +
  los reclamados por ella) + clasificacion de la seleccion actual.
- apply(doc_name, receipt_names): reclama/libera recibos y los vincula a la
  factura (queda NO definitiva). NUNCA aprueba: la aprobacion es siempre
  manual, para que el usuario pueda revisar, cambiar los recibos o decidir no
  aprobar.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.documenteme._approve_base import _has_permission
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.documenteme.receipt_bank import DEFAULT_EPSILON
from qp_supplier_front.uses_cases.documenteme.receipt_selection import (
    classify_selection,
    select_claim_release,
    sum_selected,
    validate_apply,
)

DOC_FIELDS = [
    "name",
    "nvfac_nume",
    "nvfac_orde",
    "nvfac_stot",
    "nvfac_esta",
    "nvfac_conv",
]


def _components():
    return runtime.resolve()


def _resolve_doc(doc_name, data):
    if not doc_name:
        return None
    if data is not None:
        docs = data.get_all(
            "qp_SP_DocumentDetail",
            filters={"name": doc_name},
            fields=DOC_FIELDS,
        )
        return docs[0] if docs else None
    docs = frappe.get_all(
        "qp_SP_DocumentDetail",
        filters={"name": doc_name},
        fields=DOC_FIELDS,
    )
    return docs[0] if docs else None


def _banco_response(doc, bank):
    claimed_names = [
        row.get("name") for row in bank if row.get("claimed_by_me")
    ]
    current_sum = sum_selected(
        bank, claimed_names, doc.get("nvfac_stot")
    )
    return {
        "stot": doc.get("nvfac_stot") or 0,
        "current_sum": current_sum,
        "classification": classify_selection(
            doc.get("nvfac_stot"), current_sum, DEFAULT_EPSILON
        ),
        "receipts": bank,
    }


@frappe.whitelist()
def get_bank(doc_name):
    components = _components()
    data = components.get("data")
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para ver el banco de recepciones")
            return

        doc = _resolve_doc(doc_name, data)
        if not doc:
            response(404, "Factura no encontrada")
            return

        bank = components["receipt_bank_for_invoice_fn"](
            doc.get("nvfac_orde"), doc.get("nvfac_nume")
        )
        response(200, "ok", _banco_response(doc, bank))

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al consultar el banco de recepciones: {}".format(str(error)))


@frappe.whitelist()
def apply(doc_name, receipt_names=None):
    components = _components()
    data = components.get("data")
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para aplicar recibos")
            return

        receipt_names = parse_json(receipt_names) or []

        doc = _resolve_doc(doc_name, data)
        if not doc:
            response(404, "Factura no encontrada")
            return

        bank = components["receipt_bank_for_invoice_fn"](
            doc.get("nvfac_orde"), doc.get("nvfac_nume")
        )
        claimed_names = [
            row.get("name") for row in bank if row.get("claimed_by_me")
        ]

        # Liberar todo: sin seleccion pero con recibos previamente vinculados
        # (el usuario los desmarca y aplica para dejarlos de nuevo al pool).
        release_only = (not receipt_names and bool(claimed_names))
        if release_only:
            classification = "parcial"
        else:
            ok, error, classification = validate_apply(
                doc, receipt_names, bank, DEFAULT_EPSILON
            )
            if not ok:
                response(400, error, {"classification": classification})
                return

        to_claim, to_release = select_claim_release(claimed_names, receipt_names)

        failed = []
        if to_claim:
            failed = components["claim_receipts_fn"](doc, to_claim) or []
        if failed:
            response(
                409,
                (
                    "Algunos recibos ya fueron tomados por otra factura y no "
                    "se aplico nada: {}".format(", ".join(failed))
                ),
            )
            return

        if to_release:
            components["release_receipts_fn"](doc, to_release)

        _commit(data)

        if release_only:
            response(
                200,
                (
                    "Se liberaron los recibos asociados a la factura; "
                    "la factura vuelve a quedar disponible para el flujo "
                    "automático."
                ),
                {"classification": classification, "claimed": receipt_names},
            )
            return

        # Aplicar SOLO vincula los recibos a la factura (queda NO definitiva):
        # la aprobacion es siempre manual, para que el usuario pueda revisar,
        # cambiar los recibos o decidir no aprobar.
        if classification == "parcial":
            message = (
                "El monto seleccionado no cubre el total de la factura. Los "
                "recibos quedaron aplicados; aprueba la factura manualmente "
                "cuando lo decidas."
            )
        elif classification == "excede":
            message = (
                "El monto seleccionado excede el total de la factura. Los "
                "recibos quedaron aplicados completos; aprueba la factura "
                "manualmente cuando lo decidas."
            )
        else:
            message = (
                "Recibos aplicados a la factura. Revisalos y aprueba la "
                "factura manualmente cuando lo decidas."
            )
        response(
            200,
            message,
            {"classification": classification, "claimed": receipt_names},
        )

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aplicar los recibos: {}".format(str(error)))


def _commit(data):
    if data is not None and data.is_in_memory:
        data.commit()
    else:
        frappe.db.commit()