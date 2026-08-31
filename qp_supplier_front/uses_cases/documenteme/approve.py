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
from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    RULE_NO_ACTION,
    has_po_match,
    has_receipt_match,
    should_auto_reject,
)
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice
from qp_supplier_front.uses_cases.documenteme.receipt_bank import (
    DEFAULT_EPSILON,
    MAX_INVOICES_PER_OC_GROUP,
    MAX_MATCHES_PER_INVOICE,
    pack_oc_group,
    solve_receipt_bank,
    unconsumed_receipts,
)

FINAL_STATES = ("A", "R")

ANALYSIS_STATES = ("E", "V", "T")

# Marcador que BC devuelve cuando la factura del proveedor ya existe en BC.
# El numero que menciona el mensaje es el NoFacturaProveedor (no el codigo
# BC); al llegar este error el codigo BC no es recuperable y no se debe
# reintentar la creacion.
ALREADY_REGISTERED_MARK = "ya existe la factura"


def _no_order_warning():
    return "La factura no tiene orden de compra"


def _order_not_exists_warning(purchase_order):
    return "La orden de compra {} no existe".format(purchase_order)


def _no_receipts_warning(purchase_order):
    return "No se encontraron recepciones para la orden de compra {}".format(
        purchase_order
    )


def _no_match_warning(invoice_total):
    return (
        "No existe una combinación de recepciones que coincida con el total "
        "de la factura ({})".format(invoice_total)
    )


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


def _receipt_for_po_from_bank(receipt_bank_fn):
    """Callback escalar (total o None) derivado de un banco de recepciones.

    Permite reutilizar has_receipt_match (que espera un total o None) sobre
    la logica del banco: None cuando no hay recepciones no consumidas.
    """
    if receipt_bank_fn is None:
        return lambda purchase_order: None

    def receipt_for_po(purchase_order):
        bank = receipt_bank_fn(purchase_order) or []
        unconsumed = [r for r in bank if not r.get("qp_invoice")]
        if not unconsumed:
            return None
        return sum(float(r.get("amount") or 0) for r in unconsumed)

    return receipt_for_po


def _get_cash_registrable_warnings(doc, po_exists_fn, receipts_total_fn, resolve_rule_fn):
    """Advertencias de la regla de rechazo aplicadas a una factura de CONTADO.

    Las facturas de contado no se rechazan, pero si la regla activa (proveedor
    o default de MasterSetup) exige OC/recibo y la factura no lo cumple, NO
    se aprueba automaticamente y pasa a asignacion. Con "no_action" o sin
    regla configurada, el contado se aprueba sin validar OC ni recibo.
    """
    if resolve_rule_fn is None:
        return []

    rule = resolve_rule_fn(doc)
    if not rule:
        return []

    rule_code = rule.get("rule_code")
    if not rule_code or rule_code == RULE_NO_ACTION:
        return []

    po_match = has_po_match(doc, po_exists_fn)
    receipt_match = has_receipt_match(doc, receipts_total_fn)
    if should_auto_reject(po_match, receipt_match, rule_code):
        return [
            "La factura de contado no cumple la regla de rechazo configurada "
            "({}), por lo que no se aprueba automaticamente y debe asignarse".format(
                rule_code
            )
        ]

    return []


def get_registrable_warnings(doc, po_exists_fn, receipt_bank_fn, resolve_rule_fn=None, epsilon=DEFAULT_EPSILON):
    """Retorna todas las violaciones que impedirian la aprobacion automatica.

    Devuelve una lista de mensajes (una por regla incumplida) para la regla
    factura - orden - recepcion + montos. La validacion de montos se hace
    contra el banco de recepciones no consumidas: la factura solo es
    registrable si existe una combinacion exacta (epsilon) de recepciones.

    Las facturas de CONTADO relajan OC y recibos/montos salvo que la regla de
    rechazo configurada exija OC/recibo: en ese caso la violacion bloquea la
    aprobacion automatica y la factura debe asignarse.
    """
    if is_cash_invoice(doc.get("nvfac_conv")):
        return _get_cash_registrable_warnings(
            doc,
            po_exists_fn,
            _receipt_for_po_from_bank(receipt_bank_fn),
            resolve_rule_fn,
        )

    purchase_order = doc.get("nvfac_orde")
    if not purchase_order:
        return [_no_order_warning()]

    if not po_exists_fn(purchase_order):
        return [_order_not_exists_warning(purchase_order)]

    bank = receipt_bank_fn(purchase_order) or []
    if not unconsumed_receipts(bank):
        return [_no_receipts_warning(purchase_order)]

    invoice_total = doc.get("nvfac_stot") or 0
    if solve_receipt_bank(invoice_total, bank, epsilon) is None:
        return [_no_match_warning(invoice_total)]

    return []


def validate_registrable(doc, po_exists_fn, receipt_bank_fn, resolve_rule_fn=None, epsilon=DEFAULT_EPSILON):
    """Valida la regla factura - orden - recepcion + montos.

    Retorna (ok, error).

    - Estados definitivos o no registrables (BCC/PA/PR) siempre bloquean:
      evita reenviar facturas ya creadas en BC o en proceso.
    - Facturas de CREDITO: se exige orden de compra existente y una
      combinacion exacta de recepciones no consumidas que cubra el total de
      la factura (las facturas a credito se respaldan en recepciones).
    - Facturas de CONTADO: se relaja la validacion de OC y recibos/montos,
      salvo que la regla de rechazo activa (resolve_rule_fn) exija OC/recibo:
      en ese caso la factura debe cumplirla para aprobarse.
    """
    blocker = get_registrable_blockers(doc)
    if blocker:
        return False, blocker

    warnings = get_registrable_warnings(
        doc, po_exists_fn, receipt_bank_fn, resolve_rule_fn=resolve_rule_fn, epsilon=epsilon
    )
    first_warning = warnings[0] if warnings else ""
    if first_warning:
        return False, first_warning

    return True, ""


def collect_registrable_violations(docs, po_exists_fn, receipt_bank_fn, resolve_rule_fn=None, epsilon=DEFAULT_EPSILON):
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
        warnings = get_registrable_warnings(
            doc, po_exists_fn, receipt_bank_fn, resolve_rule_fn=resolve_rule_fn, epsilon=epsilon
        )
        if warnings:
            violations.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "violations": warnings,
            })
    return violations


def validate_registrables(docs, po_exists_fn, receipt_bank_fn, resolve_rule_fn=None, epsilon=DEFAULT_EPSILON):
    valid = []
    errors = []
    for doc in (docs or []):
        ok, error = validate_registrable(
            doc, po_exists_fn, receipt_bank_fn, resolve_rule_fn=resolve_rule_fn, epsilon=epsilon
        )
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


def homologate_lines(detail_lines, homologation_map, order_no="", receiving_no=""):
    """Mapea lineas de la factura del proveedor a lineas BC homologadas.

    Para cada linea de detalle usa nvpro_codi (codigo del proveedor) y lo
    traduce al codigo BC (bc_item_code) usando el mapa de homologacion.

    Retorna (lines, missing_codes):
    - lines: listas normalizadas (item_code, qty, rate, idx) listas para el
      payload. Las lineas sin nvpro_codi o sin homologacion se omiten.
    - missing_codes: lista de codigos de proveedor sin homologacion.

    El JSON a BC lleva la informacion que la factura realmente tiene: si el
    contado no tiene OC/recibo van vacios (BC decide); si solo tiene OC se
    incluye NoPedido (order_no) con NoRecepcion vacio.
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
            "receiving_no": receiving_no,
            "order_no": order_no,
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


def _scalar_bank_fn(receipts_total_fn):
    """Convierte el callback escalar (legacy) en un banco de una sola recepcion.

    Mantiene compatibilidad con los consumidores que inyectan
    receipts_total_fn: un total se representa como una unica recepcion
    sintetica de ese monto, y None como banco vacio.
    """
    if receipts_total_fn is None:
        return lambda purchase_order: []

    def bank_fn(purchase_order):
        total = receipts_total_fn(purchase_order)
        if total is None:
            return []
        return [{
            "name": "scalar:{}".format(purchase_order),
            "amount": total,
            "date": "",
            "qp_invoice": None,
        }]

    return bank_fn


def _allocate_registrables(docs, po_exists_fn, receipt_bank_fn, epsilon, resolve_rule_fn=None):
    """Valida y asigna el banco de recepciones por orden de compra.

    Separa las facturas de contado (sin banco) y agrupa las de credito por
    orden de compra; para cada grupo asigna combinaciones exactas de
    recepciones no consumidas maximizando facturas completadas (pack_oc_group).

    Las facturas de CONTADO se admiten salvo que la regla de rechazo activa
    (resolve_rule_fn) exija OC/recibo y la factura no lo cumpla: en ese caso
    caen a error para pasar a asignacion.

    Retorna (valid, errors, allocation) donde allocation mapea doc name ->
    lista de recepciones asignadas. Una factura sin combinacion exacta no
    consume nada y cae a error (variacion 3: advertencia -> asignacion).
    """
    valid = []
    errors = []
    allocation = {}
    credit_order = []
    credit_groups = {}

    for doc in (docs or []):
        blocker = get_registrable_blockers(doc)
        if blocker:
            errors.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "error": blocker,
            })
            continue
        if is_cash_invoice(doc.get("nvfac_conv")):
            warnings = _get_cash_registrable_warnings(
                doc,
                po_exists_fn,
                _receipt_for_po_from_bank(receipt_bank_fn),
                resolve_rule_fn,
            )
            if warnings:
                errors.append({
                    "nvfac_nume": doc.get("nvfac_nume"),
                    "error": warnings[0],
                })
            else:
                valid.append(doc)
            continue
        purchase_order = doc.get("nvfac_orde")
        if not purchase_order:
            errors.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "error": _no_order_warning(),
            })
            continue
        if not po_exists_fn(purchase_order):
            errors.append({
                "nvfac_nume": doc.get("nvfac_nume"),
                "error": _order_not_exists_warning(purchase_order),
            })
            continue
        if purchase_order not in credit_groups:
            credit_groups[purchase_order] = []
            credit_order.append(purchase_order)
        credit_groups[purchase_order].append(doc)

    for purchase_order in credit_order:
        group = credit_groups[purchase_order]
        bank = receipt_bank_fn(purchase_order) or []
        if not unconsumed_receipts(bank):
            for doc in group:
                errors.append({
                    "nvfac_nume": doc.get("nvfac_nume"),
                    "error": _no_receipts_warning(purchase_order),
                })
            continue
        packed = pack_oc_group(
            group,
            bank,
            epsilon,
            MAX_INVOICES_PER_OC_GROUP,
            MAX_MATCHES_PER_INVOICE,
        )
        for doc in group:
            matched = packed.get(doc.get("nvfac_nume"))
            if matched is None:
                errors.append({
                    "nvfac_nume": doc.get("nvfac_nume"),
                    "error": _no_match_warning(doc.get("nvfac_stot") or 0),
                })
            else:
                allocation[doc.get("name")] = matched
                valid.append(doc)

    return valid, errors, allocation


def approve_documents(
    doc_names,
    get_docs_fn,
    get_lines_fn,
    get_headquarter_fn,
    po_exists_fn,
    receipts_total_fn=None,
    send_request_fn=None,
    parse_doc_numbers_fn=None,
    persist_invoice_fn=None,
    mark_registered_fn=None,
    mark_error_fn=None,
    commit_fn=None,
    now=None,
    mark_duplicate_registered_fn=None,
    force=False,
    resolve_rule_fn=None,
    receipt_bank_fn=None,
    consume_receipts_fn=None,
    epsilon=DEFAULT_EPSILON,
):
    """Aprueba en lote las facturas: un solo envio a BC con array.

    Flujo:
    1. Valida cada factura (regla factura - OC - recepcion, relajada para
       contado). Con receipt_bank_fn inyectado la validacion es batch-aware
       por orden de compra y usa el banco de recepciones no consumidas
       (pack_oc_group); las facturas sin combinacion exacta caen a error.
       Con force=True (aprobacion manual con confirmacion del usuario) se
       ignoran las advertencias de OC - recepcion - montos, pero los bloqueos
       duros (estados definitivos/en proceso) siguen impidiendo la aprobacion.
       El modo forzado NUNCA consume recepciones: sin combinacion exacta la
       factura no marca ningun recibo y el banco queda intacto.
    2. Resuelve las lineas de cada factura via get_lines_fn(doc).
    3. Construye un solo payload (array) y lo envia a BC.
    4. Las facturas con doc_number se persisten y marcan "BCC"; sus
       recepciones asignadas se consumen via consume_receipts_fn (solo las
       facturas realmente persistidas). Las que fallan (o duplicadas) no
       consumen y se registran via mark_error_fn / mark_duplicate_registered_fn.

    Retorna {"approved": [...], "errors": [...]}.
    """
    docs = get_docs_fn(doc_names)

    if force:
        valid, errors = _split_by_blockers(docs)
        allocation = {}
    elif receipt_bank_fn is not None:
        valid, errors, allocation = _allocate_registrables(
            docs, po_exists_fn, receipt_bank_fn, epsilon,
            resolve_rule_fn=resolve_rule_fn,
        )
    else:
        valid, errors = validate_registrables(
            docs, po_exists_fn, _scalar_bank_fn(receipts_total_fn),
            resolve_rule_fn=resolve_rule_fn, epsilon=epsilon,
        )
        allocation = {}

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
            matched = allocation.get(doc.get("name"))
            if consume_receipts_fn is not None and matched:
                consume_receipts_fn(
                    doc, [receipt.get("name") for receipt in matched]
                )
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
