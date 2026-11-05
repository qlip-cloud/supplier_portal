# -*- coding: utf-8 -*-
"""
credit_note_bc.py (documenteme)
===============================
Nucleo puro del armado de lineas de una Nota Credito para Business Central.

En BC no se usa homologacion: el ``NoProducto`` sale de las lineas de
recepcion de la factura de compra referenciada y, si no tiene recepciones, de
las lineas de su orden de compra. La cantidad y el precio salen del detalle de
la NC. Las recepciones pueden repetir el mismo producto (una fila por recibo),
por eso el banco se consolida por ``item_code`` antes de emparejar.

Este modulo no importa Frappe, por lo que se testea en aislamiento.
"""


def _normalize(value):
    return " ".join(str(value or "").strip().lower().split())


def _consolidate_products(bank_lines):
    """Productos distintos del banco de la referencia (orden de aparicion).

    Una factura puede tener varias lineas del mismo producto (una por
    recepcion). Para la NC solo importa el codigo BC del producto: se
    desduplica por ``item_code``.
    """
    products = []
    seen = set()
    for line in (bank_lines or []):
        code = str(line.get("item_code") or "").strip()
        if not code:
            continue
        key = code.lower()
        if key in seen:
            continue
        seen.add(key)
        products.append({
            "item_code": code,
            "item_name": line.get("item_name") or "",
            "description": line.get("description") or "",
        })
    return products


def _match_product(nc_line, products, position, nc_count):
    """Elige el producto BC de la referencia para una linea de la NC.

    Prioridad: codigo BC (si la NC ya lo trae), nombre/descripcion, un unico
    producto en la referencia, o asignacion posicional cuando hay la misma
    cantidad de lineas que de productos distintos.
    """
    code = _normalize(nc_line.get("item_code"))
    if code:
        for product in products:
            if _normalize(product.get("item_code")) == code:
                return product

    description = _normalize(nc_line.get("description"))
    if description:
        for product in products:
            if (
                _normalize(product.get("item_name")) == description
                or _normalize(product.get("description")) == description
            ):
                return product

    if len(products) == 1:
        return products[0]
    if len(products) == nc_count:
        return products[position]
    return None


def build_receipt_lines(bank_lines):
    """Lineas del payload BC tomadas de la recepcion/OC de la referencia.

    Solicitado por negocio: la NC se arma con las lineas de la recepcion (o
    de la OC si no hay recepcion) de la factura referenciada, usando su
    producto, cantidad y precio. NO se consolida por producto: dos recepciones
    del mismo item generan dos lineas.

    Alternativa (si negocio pide una linea por producto de la NC): usar
    ``resolve_credit_note_lines`` con el detalle de la NC.
    """
    lines = []
    for line in (bank_lines or []):
        code = str(line.get("item_code") or "").strip()
        if not code:
            continue
        lines.append({
            "item_code": code,
            "qty": line.get("qty") or 0,
            "rate": line.get("rate") or 0,
            "type": "Item",
        })
    if not lines:
        return [], (
            "La factura de compra referenciada no tiene recepciones ni orden "
            "de compra para tomar los productos"
        )
    return lines, ""


def resolve_credit_note_lines(nc_lines, bank_lines):
    """Alternativa: arma las lineas BC a partir del detalle de la NC y del banco.

    No es la ruta actual (negocio pidio las lineas de la recepcion/OC, ver
    ``build_receipt_lines``). Se conserva para poder volver a este criterio.

    nc_lines: [{item_code, description, qty, rate, ...}]
    bank_lines: [{item_code, item_name, description, receiving_no, order_no}]

    El ``item_code`` del payload SIEMPRE es el producto BC de la referencia.
    La cantidad y el precio salen de la NC. Retorna (payload_lines, error); si
    no hay forma determinista de asignar un producto, no se envia la nota.
    """
    if not nc_lines:
        return [], "La nota credito no tiene lineas para enviar"

    products = _consolidate_products(bank_lines)
    if not products:
        return [], (
            "La factura de compra referenciada no tiene recepciones ni orden "
            "de compra para tomar los productos"
        )

    payload = []
    for index, nc_line in enumerate(nc_lines):
        product = _match_product(
            nc_line, products, index, len(nc_lines)
        )
        if product is None:
            return [], (
                "No se pudo resolver el producto BC de la linea {} de la nota "
                "credito ({}): no coincide con la recepcion/OC de la "
                "referencia"
            ).format(index + 1, nc_line.get("item_code") or "-")
        payload.append({
            "item_code": product.get("item_code") or "",
            "qty": nc_line.get("qty") or 0,
            "rate": nc_line.get("rate") or 0,
            "type": "Item",
        })
    return payload, ""
