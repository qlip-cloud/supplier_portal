# -*- coding: utf-8 -*-
"""
receipt_selection.py (documenteme) — infraestructura
====================================================
Seleccion manual del banco de recepciones para una factura documenteme.

- get_bank(doc_name): banco visible para la factura (recibos no reclamados +
  los reclamados por ella) + clasificacion de la seleccion actual.
- apply(doc_name, receipt_names): reclamar/liberar recibos segun el check de
  la UI. Si la seleccion cubre el subtotal (completo) se dispara el proceso de
  aprobacion (crear en BC -> BCC -> confirmacion); si es parcial solo se
  reservan los recibos (la factura queda no definitiva).
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.documenteme._approve_base import (
    _has_permission,
    run_approve_with_receipts,
)
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
    current_sum = sum_selected(bank, claimed_names)
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

        if classification == "parcial":
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
            response(
                200,
                (
                    "El monto seleccionado no cubre el total. Los recibos "
                    "quedaron reservados para esta factura y no estarán "
                    "disponibles para otras."
                ),
                {"classification": classification, "claimed": receipt_names},
            )
            return

        result = run_approve_with_receipts(
            [doc.get("name")], {doc.get("name"): receipt_names}
        )
        errors = result.get("errors") or []
        if errors:
            detail = ", ".join(
                "{}: {}".format(err.get("nvfac_nume"), err.get("error"))
                for err in errors
            )
            response(500, "Error al aprobar: {}".format(detail), result)
            return

        response(
            200,
            (
                "Recibos aplicados. La factura se está aprobando "
                "automáticamente."
            ),
            result,
        )

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aplicar los recibos: {}".format(str(error)))


def _commit(data):
    if data is not None and data.is_in_memory:
        data.commit()
    else:
        frappe.db.commit()