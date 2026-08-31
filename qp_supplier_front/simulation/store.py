# -*- coding: utf-8 -*-
"""
store.py (documenteme simulation)
=================================
Almacen en memoria para los doctypes del flujo documenteme en modo simulacion.

Es la implementacion "in-memory" del contrato de datos (domain/ports): todos
los doctypes del modulo (qp_SP_DocumentDetail y childs, qp_SP_DocumentSyncLine,
qp_SP_DocumentSyncLog, qp_SP_PurchaseInvoice, qp_SP_PurchaseInvoiceBC) viven
en memoria durante la sesion; nada se escribe en la base de datos real.

Provee un motor de query minimo compatible con las operaciones que usa el
flujo: filtros (=, in, like, is not set, comparativos), order_by, paginacion,
pluck, get_value, set_value, exists, count y delete. Las child tables son
doctypes propios con campo "parent" (misma semantica que Frappe).
"""


def _match_value(value, operator, expected):
    """True si value satisface el filtro Frappe normalizado."""
    if operator == "is":
        if expected == "not set":
            return value is None or value == ""
        if expected == "set":
            return value is not None and value != ""
        return value == expected
    if value is None:
        return False
    if operator == "=":
        return str(value) == str(expected)
    if operator == "in":
        return value in set(expected or [])
    if operator == "not in":
        return value not in set(expected or [])
    if operator == "like":
        return _like_match(str(value), str(expected or ""))
    if operator in (">", "<", ">=", "<="):
        try:
            left, right = float(value), float(expected)
        except (TypeError, ValueError):
            return False
        return {
            ">": left > right,
            "<": left < right,
            ">=": left >= right,
            "<=": left <= right,
        }[operator]
    return str(value) == str(expected)


def _like_match(value, pattern):
    if pattern.startswith("%") and pattern.endswith("%"):
        return pattern[1:-1] in value
    if pattern.endswith("%"):
        return value.startswith(pattern[:-1])
    if pattern.startswith("%"):
        return value.endswith(pattern[1:])
    return value == pattern


def _normalize_filter(value):
    """Convierte {field: value} a (operador, esperado) tipo Frappe."""
    if isinstance(value, list) and len(value) == 2 and value[0] in (
            "=", "in", "not in", "like", ">", "<", ">=", "<=", "is"):
        return value[0], value[1]
    return "=", value


def _row_matches(row, filters):
    for field, raw in (filters or {}).items():
        op, expected = _normalize_filter(raw)
        if not _match_value(row.get(field), op, expected):
            return False
    return True


def _order_value(row, field):
    value = row.get(field)
    if value is None or value == "":
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


class MemoryStore(object):
    """Store generico: doctype -> {name: row(dict)}."""

    def __init__(self):
        self._tables = {}

    def has_doctype(self, doctype):
        return doctype in self._tables

    def insert(self, doctype, row, name=None):
        table = self._tables.setdefault(doctype, {})
        name = name or row.get("name")
        if not name:
            # Autoname minimo determinista por insercion: CONT-<seq>
            name = "{}-{}".format(doctype, len(table) + 1)
        row = dict(row)
        row["name"] = name
        table[name] = row
        return name

    def get(self, doctype, name):
        row = self._tables.get(doctype, {}).get(_norm(name))
        return _copy(row)

    def exists(self, doctype, name_or_filters):
        if isinstance(name_or_filters, dict):
            return self.count(doctype, name_or_filters) > 0
        return _norm(name_or_filters) in self._tables.get(doctype, {})

    def delete(self, doctype, name):
        table = self._tables.get(doctype)
        if table is None:
            return
        table.pop(_norm(name), None)

    def update(self, doctype, name, row):
        table = self._tables.get(doctype, {})
        key = _norm(name)
        if key not in table:
            return None
        merged = dict(table[key])
        merged.update(row)
        merged["name"] = key
        table[key] = merged
        return _copy(merged)

    def set_value(self, doctype, name_or_filters, field, value):
        if isinstance(name_or_filters, dict):
            rows = self.query(doctype, filters=name_or_filters)
            for row in rows:
                self.update(doctype, row["name"], {field: value})
            return len(rows)
        return self.update(doctype, name_or_filters, {field: value}) is not None

    def get_value(self, doctype, filters_or_name, field=None):
        if isinstance(filters_or_name, dict):
            rows = self.query(doctype, filters=filters_or_name, limit=1)
            if not rows:
                return None
            row = rows[0]
        else:
            row = self.get(doctype, filters_or_name)
            if row is None:
                return None
        if field is None:
            return row
        return row.get(field)

    def count(self, doctype, filters=None):
        return len(self.query(doctype, filters=filters))

    def query(self, doctype, filters=None, fields=None, order_by=None,
              start=0, page_length=None, pluck=None, limit=None):
        rows = [
            row for row in self._tables.get(doctype, {}).values()
            if _row_matches(row, filters)
        ]
        rows = _sort_rows(rows, order_by)
        if limit is not None:
            rows = rows[:limit]
        else:
            start = start or 0
            if page_length is not None:
                rows = rows[start:start + page_length]
            elif start:
                rows = rows[start:]
        if pluck:
            return [row.get(pluck) for row in rows]
        if fields and fields != ["*"]:
            out = []
            for row in rows:
                item = {field: row.get(field) for field in fields}
                out.append(item)
            return out
        return [_copy(row) for row in rows]

    def all_doctypes(self):
        return sorted(self._tables.keys())


def _norm(name):
    return name if isinstance(name, str) else str(name)


def _copy(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def _sort_rows(rows, order_by):
    if not order_by:
        return rows
    clauses = []
    for part in order_by.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        field = bits[0]
        desc = len(bits) > 1 and bits[1].lower() == "desc"
        clauses.append((field, desc))
    if not clauses:
        return rows
    result = list(rows)
    for field, desc in reversed(clauses):
        result.sort(
            key=lambda row, f=field: (isinstance(row.get(f), (int, float)),
                                      _order_value(row, f)),
            reverse=desc,
        )
    return result