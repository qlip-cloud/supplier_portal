# -*- coding: utf-8 -*-
"""
approve.py (documenteme)
========================
Nucleo puro de la aprobacion (registro en BC) de facturas documenteme.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(DB, API, persistencia) son inyectadas como callbacks.

Modelo de estados:
- Estados definitivos: "A" (Registrado) y "R" (Rechazada). Nunca se aprueban.
- Analisis: toda factura no definitiva que cumpla la regla
  factura - orden - recepcion y la suma de montos pasa a estado "V".
- Aprobacion: las facturas en "V" se envian a BC (en lote, un solo payload
  con array) y pasan a estado "A".

Sirve tanto para la aprobacion manual (recurso approve) como para la
automatica (recurso auto_approve), replicando el patron del rechazo.
"""

from qp_supplier_front.constant.endpoint import CREATE_PURCHASE_ORDER

FINAL_STATES = ("A", "R")

ANALYSIS_STATES = ("E", "V", "T")


def is_definitive(status):
    return status in FINAL_STATES


def validate_registrable(doc, po_exists_fn, receipts_total_fn):
    """Valida la regla factura - orden - recepcion + montos.

    Retorna (ok, error). El total de recepciones debe cubrir exactamente
    el total de la factura.
    """
    if is_definitive(doc.get("nvfac_esta")):
        return False, "La factura está en un estado definitivo"

    purchase_order = doc.get("nvfac_orde")
    if not purchase_order:
        return False, "La factura no tiene orden de compra"

    if not po_exists_fn(purchase_order):
        return False, "La orden de compra {} no existe".format(purchase_order)

    receipts_total = receipts_total_fn(purchase_order)
    if receipts_total is None:
        return False, (
            "No se encontraron recepciones para la orden de compra {}"
        ).format(purchase_order)

    invoice_total = doc.get("nvfac_totp") or 0
    if receipts_total != invoice_total:
        return False, (
            "La sumatoria de recepciones ({}) no coincide con el total "
            "de la factura ({})".format(receipts_total, invoice_total)
        )

    return True, ""


def validate_registrables(docs, po_exists_fn, receipts_total_fn):
    valid = []
    errors = []
    for doc in (docs or []):
        ok, error = validate_registrable(doc, po_exists_fn, receipts_total_fn)
        if ok:
            valid.append(doc)
        else:
            errors.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "error": error,
            })
    return valid, errors


def _to_date(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


def _build_vendor_invoice_line(line):
    return {
        "NoProducto": line.get("item_code") or "",
        "cantidad": line.get("qty") or 0,
        "Precio": line.get("qp_unit_cost") or 0,
        "NoLineaRecepcion": str(line.get("idx") or "") ,
        "NoRecepcion": line.get("receiving_no") or "",
        "NoPedido": line.get("order_no") or "",
    }


def _build_invoice(doc, lines):
    invoice_date = _to_date(doc.get("nvfac_fech"))
    return {
        "invoiceDate": invoice_date,
        "postingDate": invoice_date,
        "vendorNumber": doc.get("nvpro_ndoc"),
        "puntofacturacion": "",
        "NoFacturaProveedor": doc.get("nvfac_nume"),
        "Cufe": doc.get("nvfac_cufe") or "",
        "tipoFacturaDoc": "Estándar",
        "formaPago": "",
        "dimensionSetLines": [
            {"code": "TERCERO", "valueCode": doc.get("nvpro_ndoc")}
        ],
        "vendorInvoiceLine": [
            _build_vendor_invoice_line(line)
            for line in (lines or [])
        ],
    }


def build_payload(docs, get_lines_fn):
    """Construye el payload de BC como array de facturas (una por doc).

    Cada linea se origina de las recepciones (Purchase Receipt / Item) y
    NoLineaRecepcion es el idx del Purchase Receipt Item.
    """
    payload = []
    for doc in (docs or []):
        lines = get_lines_fn(doc.get("nvfac_orde"))
        payload.append(_build_invoice(doc, lines))
    return payload


def get_error_message(response):
    if not isinstance(response, dict):
        return str(response)
    if "#text" in response:
        return get_error_message(response.get("#text"))
    return (
        response.get("Description")
        or response.get("Message")
        or response.get("message")
        or response.get("error")
        or response.get("Error")
        or str(response)
    )


def is_error_response(response, status):
    if status not in (200, 201):
        return True
    if isinstance(response, dict) and response.get("Result") == 1:
        return True
    return False


def _invoice_result_at(invoice_results, idx):
    if not invoice_results or idx >= len(invoice_results):
        return {"doc_number": None, "error": "BC no devolvió resultado para la factura"}
    result = invoice_results[idx]
    if not isinstance(result, dict):
        return {"doc_number": None, "error": "Resultado de BC inválido"}
    return result


def _record_error(errors, mark_error_fn, doc, error):
    """Acumula el error y persiste la alerta en la factura."""
    errors.append({
        "nvfac_nume": doc.get("nvfac_nume"),
        "error": error,
    })
    if mark_error_fn is not None:
        mark_error_fn(doc, error)


def approve_documents(
    doc_names,
    get_docs_fn,
    get_lines_fn,
    po_exists_fn,
    receipts_total_fn,
    send_request_fn,
    parse_doc_numbers_fn,
    persist_invoice_fn,
    mark_registered_fn,
    mark_error_fn,
    commit_fn,
    now,
):
    """Aprueba en lote las facturas: un solo envio a BC con array.

    BC devuelve un resultado por factura (doc_number o error) en el mismo
    orden del payload. Las que traen doc_number se persisten y marcan "A";
    las que fallan (error global o por factura) quedan en "V" para reintentar
    y se registra una alerta (mark_error_fn) en la factura.

    Retorna {"approved": [...], "errors": [...]}.
    """
    docs = get_docs_fn(doc_names)

    valid, errors = validate_registrables(docs, po_exists_fn, receipts_total_fn)

    if not valid:
        return {"approved": [], "errors": errors}

    payload = build_payload(valid, get_lines_fn)

    try:
        response, status = send_request_fn(
            endpoint_code=CREATE_PURCHASE_ORDER,
            payload=payload,
        )
    except Exception as e:
        for doc in valid:
            _record_error(errors, mark_error_fn, doc, str(e))
        return {"approved": [], "errors": errors}

    if is_error_response(response, status):
        message = get_error_message(response)
        for doc in valid:
            _record_error(errors, mark_error_fn, doc, message)
        return {"approved": [], "errors": errors}

    invoice_results = parse_doc_numbers_fn(response)

    approved = []
    for idx, doc in enumerate(valid):
        result = _invoice_result_at(invoice_results, idx)
        if result.get("error"):
            _record_error(errors, mark_error_fn, doc, result.get("error"))
            continue
        doc_number = result.get("doc_number")
        try:
            persist_invoice_fn(doc, doc_number, now)
            mark_registered_fn(doc, doc_number)
        except Exception as e:
            _record_error(errors, mark_error_fn, doc, str(e))
            continue
        approved.append({
            "name": doc.get("name"),
            "nvfac_nume": doc.get("nvfac_nume"),
            "doc_number": doc_number or "",
        })

    commit_fn()

    return {"approved": approved, "errors": errors}
