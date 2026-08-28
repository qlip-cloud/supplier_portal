# -*- coding: utf-8 -*-
"""
approve.py (documenteme)
========================
Nucleo puro de la aprobacion (registro en BC) de facturas documenteme.
No tiene imports a Frappe. Todas las dependencias de infraestructura
(DB, API, persistencia) son inyectadas como callbacks.

Modelo de estados (tabla de estatus actual):
- "E": Registrado.
- "V": Analisis / no definitivo (Nvfac_ueve != 031/033).
- "A": Aprobado (final, tras notificar 033 a documenteme).
- "R": Rechazado (final).
- "BCC": Creada en BC (tras crear la factura en BC, esperando confirmacion).
- "PA": En proceso de Aprobacion en documenteme.
- "PR": En proceso de Rechazo en documenteme.
- Analisis: toda factura no definitiva que cumpla la regla
  factura - orden - recepcion y la suma de montos pasa a estado "V".
- Creacion en BC: las facturas en "V" se envian a BC (en lote, un solo payload
  con array) y pasan a estado "BCC". La aprobacion final ("A") se alcanza
  cuando el servicio de confirmacion guarda el confirmation_id y se notifica
  la secuencia 030 -> 032 -> 033 a documenteme.

Sirve tanto para la aprobacion manual (recurso approve) como para la
automatica (recurso auto_approve), replicando el patron del rechazo.
"""

from qp_supplier_front.constant.endpoint import CREATE_PURCHASE_ORDER
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice

FINAL_STATES = ("A", "R")

ANALYSIS_STATES = ("E", "V", "T")

# Marcador que BC devuelve cuando la factura del proveedor ya existe en BC.
# El numero que menciona el mensaje es el NoFacturaProveedor (no el codigo
# BC); al llegar este error el codigo BC no es recuperable y no se debe
# reintentar la creacion.
ALREADY_REGISTERED_MARK = "ya existe la factura"


def is_definitive(status):
    return status in FINAL_STATES


def is_invoice_already_registered(error):
    """True si BC responde que la factura ya existe para el proveedor."""
    if not isinstance(error, str):
        return False
    return ALREADY_REGISTERED_MARK in error.lower()


def get_registrable_blockers(doc):
    """Retorna el motivo de bloqueo duro de una factura, o vacio si no aplica.

    Los bloqueos duros (estados definitivos o en proceso) no son anulables
    por el usuario: ni la aprobacion automatica ni la manual forzada pueden
    registrar facturas ya creadas en BC, en proceso o en estado final.
    """
    if is_definitive(doc.get("nvfac_esta")):
        return "La factura está en un estado definitivo"

    if doc.get("nvfac_esta") not in ANALYSIS_STATES:
        return (
            "La factura está en un estado no registrable ({})".format(
                doc.get("nvfac_esta")
            )
        )

    return ""


def get_registrable_warnings(doc, po_exists_fn, receipts_total_fn):
    """Retorna todas las violaciones que impedirian la aprobacion automatica.

    Devuelve una lista de mensajes (una por regla incumplida) para la regla
    factura - orden - recepcion + montos. Estas violaciones se muestran al
    usuario en la aprobacion manual y pueden ser anuladas (aprobacion
    forzada). Las facturas de CONTADO relajan OC y recibos/montos, por lo
    que sus advertencias son generadas solo si llegan a la parte de credito
    (nunca; la validacion de contado no exige estos datos).
    """
    if is_cash_invoice(doc.get("nvfac_conv")):
        return []

    warnings = []

    purchase_order = doc.get("nvfac_orde")
    if not purchase_order:
        warnings.append("La factura no tiene orden de compra")
    elif not po_exists_fn(purchase_order):
        warnings.append("La orden de compra {} no existe".format(purchase_order))

    if purchase_order:
        receipts_total = receipts_total_fn(purchase_order)
        if receipts_total is None:
            warnings.append(
                "No se encontraron recepciones para la orden de compra {}".format(
                    purchase_order
                )
            )
        else:
            invoice_total = doc.get("nvfac_stot") or 0
            if receipts_total != invoice_total:
                warnings.append(
                    "La sumatoria de recepciones ({}) no coincide con el valor "
                    "base de la factura ({})".format(receipts_total, invoice_total)
                )

    return warnings


def validate_registrable(doc, po_exists_fn, receipts_total_fn):
    """Valida la regla factura - orden - recepcion + montos.

    Retorna (ok, error).

    - Estados definitivos o no registrables (BCC/PA/PR) siempre bloquean:
      evita reenviar facturas ya creadas en BC o en proceso.
    - Facturas de CREDITO: se exige orden de compra existente y que el total
      de recepciones cubra exactamente el total de la factura (las facturas a
      credito se respaldan en recepciones).
    - Facturas de CONTADO: se relaja la validacion de OC y recibos/montos,
      porque no siempre tienen recepcion.
    """
    blocker = get_registrable_blockers(doc)
    if blocker:
        return False, blocker

    warnings = get_registrable_warnings(doc, po_exists_fn, receipts_total_fn)
    first_warning = warnings[0] if warnings else ""
    if first_warning:
        return False, first_warning

    return True, ""


def collect_registrable_violations(docs, po_exists_fn, receipts_total_fn):
    """Acumula todas las violaciones de aprobacion automatica por factura.

    Retorna una lista de dicts {"nvfac_nume", "violations": [mensaje, ...]}
    para cada factura con advertencias de la regla OC - recepcion - montos.
    Las facturas con bloqueo duro (estados definitivos/en proceso) no se
    incluyen porque no son anulables por el usuario: se mantienen fuera de
    la decision de aprobacion forzada.
    """
    violations = []
    for doc in (docs or []):
        blocker = get_registrable_blockers(doc)
        if blocker:
            continue
        warnings = get_registrable_warnings(doc, po_exists_fn, receipts_total_fn)
        if warnings:
            violations.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "violations": warnings,
            })
    return violations


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


def _build_vendor_invoice_line(line, idx="10000"):
    return {
        "NoProducto": line.get("item_code") or "",
        "cantidad": line.get("qty") or 0,
        "Precio": line.get("rate") or 0,
        "NoLineaRecepcion": idx,
        "NoRecepcion": line.get("receiving_no") or "",
        "NoPedido": line.get("order_no") or "",
    }


def homologate_lines(detail_lines, homologation_map):
    """Mapea lineas de la factura del proveedor a lineas BC homologadas.

    Para cada linea de detalle usa nvpro_codi (codigo del proveedor) y lo
    traduce al codigo BC (bc_item_code) usando el mapa de homologacion.

    Retorna (lines, missing_codes):
    - lines: listas normalizadas (item_code, qty, rate, idx) listas para el
      payload. Las lineas sin nvpro_codi o sin homologacion se omiten.
    - missing_codes: lista de codigos de proveedor sin homologacion.
    """
    lines = []
    missing_codes = []
    for i, line in enumerate(detail_lines or []):
        supplier_code = line.get("nvpro_codi")
        if not supplier_code:
            continue
        bc_item_code = (homologation_map or {}).get(supplier_code)
        if not bc_item_code:
            missing_codes.append(supplier_code)
            continue
        lines.append({
            "item_code": bc_item_code,
            "qty": line.get("nvdet_tcan") or 0,
            "rate": line.get("nvdet_valo") or 0,
            "idx": i,
            "receiving_no": "",
            "order_no": "",
        })
    return lines, missing_codes


def _build_invoice(doc, lines, headquarter):
    invoice_date = _to_date(doc.get("nvfac_fech"))
    return {
        "invoiceDate": invoice_date,
        "postingDate": invoice_date,
        "vendorNumber": doc.get("nvpro_ndoc"),
        "puntofacturacion": "",
        "NoFacturaProveedor": doc.get("nvfac_nume"),
        "Cufe": doc.get("nvfac_cufe") or "",
        "Almacen": headquarter or "",
        "tipoFacturaDoc": "Estándar",
        "formaPago": "",
        "dimensionSetLines": [
            {"code": "TERCERO", "valueCode": doc.get("nvpro_ndoc")}
        ],
        "vendorInvoiceLine": [
            _build_vendor_invoice_line(line, idx=str((i+1) * 10000))
            for i, line in enumerate(lines or [])
        ],
    }


def build_payload(docs, get_lines_fn, get_headquarter_fn):
    """Construye el payload de BC como array de facturas (una por doc).

    Cada linea se origina de las recepciones (Purchase Receipt / Item) o de
    las lineas de la factura del proveedor homologadas (contado sin recibo).
    NoLineaRecepcion es el idx de la linea. El headquarter (sede/almacen) se
    resuelve por OC via el callback inyectado.

    get_lines_fn recibe el doc y retorna (lines, error); si error no es vacio
    la factura se omite del payload.
    """
    payload = []
    for doc in (docs or []):
        lines, line_error = get_lines_fn(doc)
        if line_error:
            continue
        headquarter = get_headquarter_fn(doc.get("nvfac_orde"))
        payload.append(_build_invoice(doc, lines, headquarter))
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


def _split_by_blockers(docs):
    """Separa facturas por bloqueo duro (estados definitivos/en proceso).

    En modo forzado las advertencias de OC - recepcion - montos se ignoran,
    pero los bloqueos duros siguen impidiendo la aprobacion. Retorna
    (valid, errors) con la misma forma de validate_registrables.
    """
    valid = []
    errors = []
    for doc in (docs or []):
        blocker = get_registrable_blockers(doc)
        if blocker:
            errors.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "error": blocker,
            })
        else:
            valid.append(doc)
    return valid, errors


def approve_documents(
    doc_names,
    get_docs_fn,
    get_lines_fn,
    get_headquarter_fn,
    po_exists_fn,
    receipts_total_fn,
    send_request_fn,
    parse_doc_numbers_fn,
    persist_invoice_fn,
    mark_registered_fn,
    mark_error_fn,
    commit_fn,
    now,
    mark_duplicate_registered_fn=None,
    force=False,
):
    """Aprueba en lote las facturas: un solo envio a BC con array.

    Flujo:
    1. Valida cada factura (regla factura - OC - recepcion, relajada para
       contado). Las invalidas quedan en error y no se procesan. Con
       force=True (aprobacion manual con confirmacion del usuario) se
       ignoran las advertencias de OC - recepcion - montos, pero los bloqueos
       duros (estados definitivos/en proceso) siguen impidiendo la aprobacion.
    2. Resuelve las lineas de cada factura via get_lines_fn(doc). Las lineas
       pueden venir de las recepciones o de la factura del proveedor
       homologada (contado sin recibo / credito forzado). Si get_lines_fn
       devuelve error (p.ej. falta homologacion de un codigo), la factura
       queda en error y no se envia.
    3. Construye un solo payload (array) y lo envia a BC. BC devuelve un
       resultado por factura (doc_number o error) en el mismo orden.
    4. Las facturas con doc_number se persisten y marcan "BCC" (Creada en BC);
       las que fallan quedan para reintentar y se registra una alerta
       (mark_error_fn). Si BC responde "Ya existe la factura" (duplicada), se
       detiene el reintento llamando a mark_duplicate_registered_fn (cuando
       esta inyectado): la factura queda en "BCC" con alerta, sin referencia
       a un invoice_id que se desconoce.

    Retorna {"approved": [...], "errors": [...]}.
    """
    docs = get_docs_fn(doc_names)

    if force:
        valid, errors = _split_by_blockers(docs)
    else:
        valid, errors = validate_registrables(docs, po_exists_fn, receipts_total_fn)

    if not valid:
        return {"approved": [], "errors": errors}

    payload_docs = []
    payload = []
    for doc in valid:
        lines, line_error = get_lines_fn(doc)
        if line_error:
            _record_error(errors, mark_error_fn, doc, line_error)
            continue
        headquarter = get_headquarter_fn(doc.get("nvfac_orde"))
        payload_docs.append(doc)
        payload.append(_build_invoice(doc, lines, headquarter))

    if not payload:
        return {"approved": [], "errors": errors}

    try:
        response, status = send_request_fn(
            endpoint_code=CREATE_PURCHASE_ORDER,
            payload=payload,
        )
    except Exception as e:
        for doc in payload_docs:
            _record_error(errors, mark_error_fn, doc, str(e))
        return {"approved": [], "errors": errors}

    if is_error_response(response, status):
        message = get_error_message(response)
        for doc in payload_docs:
            _record_error(errors, mark_error_fn, doc, message)
        return {"approved": [], "errors": errors}

    invoice_results = parse_doc_numbers_fn(response)

    approved = []
    for idx, doc in enumerate(payload_docs):
        result = _invoice_result_at(invoice_results, idx)
        if result.get("error"):
            error = result.get("error")
            if (mark_duplicate_registered_fn is not None
                    and is_invoice_already_registered(error)):
                try:
                    mark_duplicate_registered_fn(doc, error, now)
                except Exception:
                    _record_error(errors, mark_error_fn, doc, error)
                    continue
                errors.append({
                    "name": doc.get("name"),
                    "nvfac_nume": doc.get("nvfac_nume"),
                    "error": error,
                    "duplicate": True,
                })
                continue
            _record_error(errors, mark_error_fn, doc, error)
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
