# -*- coding: utf-8 -*-
"""attachments.py (documenteme) - nucleo puro de adjuntos de facturas.

Funciones puras (sin frappe) para decidir y construir las filas del child
`qp_SP_DocumentAttach` de una factura documenteme:

  - guess_file_type: tipo derivado de la extension (igual criterio que
    collection_accounts._guess_file_type).
  - is_downloadable_type / count_non_xml / has_downloadable: el ZIP de
    descarga excluye XML; solo cuentan los adjuntos descargables que ademas
    existan fisicamente cuando se inyecta exists_fn.
  - build_attachment_row: fila lista para el child.
  - find_attachment / plan_attachment: evitan duplicados idempotentes.
"""

DOWNLOADABLE_EXCLUDED_TYPES = ("XML",)


def normalize_type(value):
    return str(value or "").strip().upper()


def guess_file_type(file_name):
    """Tipo derivado de la extension ("PDF", "XML"); vacio si no hay."""
    name = str(file_name or "").split("?", 1)[0]
    if "." not in name:
        return ""
    ext = name.rsplit(".", 1)[1].strip()
    return ext.upper() if ext else ""


def is_downloadable_type(file_type):
    return normalize_type(file_type) not in DOWNLOADABLE_EXCLUDED_TYPES


def count_non_xml(rows):
    return len(
        [row for row in (rows or []) if is_downloadable_type(row.get("file_type"))]
    )


def has_downloadable(rows, exists_fn=None):
    """True si hay al menos un adjunto descargable (y existente)."""
    for row in rows or []:
        if not is_downloadable_type(row.get("file_type")):
            continue
        if exists_fn is not None and not exists_fn(row):
            continue
        return True
    return False


def resolve_file_name(file_name, file_url=None):
    from posixpath import basename

    name = str(file_name or "").strip()
    if name:
        return name
    return basename(str(file_url or "").split("?", 1)[0]) or "documento"


def build_attachment_row(file_name, file_url, file_id):
    name = resolve_file_name(file_name, file_url)
    return {
        "file_name": name,
        "file_type": guess_file_type(name),
        "file_url": str(file_url or "").strip(),
        "file_id": str(file_id or "").strip(),
    }


def find_attachment(rows, file_id=None, file_url=None):
    wanted_id = str(file_id or "").strip()
    wanted_url = str(file_url or "").strip()
    for row in rows or []:
        if wanted_id and str(row.get("file_id") or "").strip() == wanted_id:
            return row
        if wanted_url and str(row.get("file_url") or "").strip() == wanted_url:
            return row
    return None


def plan_attachment(rows, row):
    """Devuelve (fila_a_agregar, existente). Nunca duplica."""
    existing = find_attachment(
        rows, file_id=row.get("file_id"), file_url=row.get("file_url")
    )
    if existing:
        return None, existing
    return row, None


def download_files(rows):
    """Adjuntos que van al ZIP: XML y no-XML (todos con archivo resoluble)."""
    return [
        row for row in (rows or [])
        if str(row.get("file_id") or "").strip()
        or str(row.get("file_url") or "").strip()
    ]


def ensure_extension(file_name, file_type):
    """Agrega la extension del tipo cuando el nombre no la trae."""
    name = str(file_name or "").strip() or "documento"
    ext = normalize_type(file_type)
    if not ext or "." in name:
        return name
    return "{0}.{1}".format(name, ext.lower())

