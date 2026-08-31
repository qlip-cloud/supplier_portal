# -*- coding: utf-8 -*-
"""
data_facade.py (documenteme simulation)
=======================================
Facade de datos para los orquestadores documenteme: expone la API Frappe
(limitada) que usan los autoprocesos. En modo real delega en frappe; en modo
simulador enruta los doctypes del modulo al MemoryStore y delega el resto
(referencias) en frappe real.

Los orquestadores reciben el facade desde runtime.resolve()["data"] y nunca
saben si es simulacion: solo llaman get_all / get_doc / db.set_value, etc.
"""

MODULE_DOCTYPES = (
    "qp_SP_DocumentDetail",
    "qp_SP_DocumentSyncLine",
    "qp_SP_DocumentSyncLog",
    "qp_SP_PurchaseInvoice",
    "qp_SP_PurchaseInvoiceBC",
    "qp_SP_DetailLine",
    "qp_SP_DetailLineTax",
    "qp_SP_DocumentAttach",
    "qp_SP_AllowanceCharge",
    "qp_SP_EventLog",
    "qp_SP_Alert",
    "qp_SP_DetailSyncAttempt",
    "qp_SP_SyncLineAssignedUser",
)


class _Real(object):
    """Delega en el modulo frappe real."""

    def __init__(self, frappe):
        self._frappe = frappe

    def get_all(self, doctype, filters=None, fields=None, order_by=None,
                limit=None, start=0, page_length=None, pluck=None,
                sort_field=None):
        return self._frappe.get_all(
            doctype, filters=filters, fields=fields, order_by=order_by,
            limit=limit)

    def get_list(self, doctype, filters=None, fields=None, order_by=None,
                 start=0, page_length=None, pluck=None):
        return self._frappe.get_list(
            doctype, filters=filters, fields=fields, order_by=order_by,
            start=start, page_length=page_length)

    def get_value(self, doctype, name_or_filters, field=None):
        if isinstance(name_or_filters, dict) and field is None:
            return self._frappe.get_value(doctype, name_or_filters)
        return self._frappe.get_value(doctype, name_or_filters, field)

    def get_doc(self, doctype, name=None, **kwargs):
        if isinstance(doctype, dict):
            kwargs = doctype
            doctype = kwargs.get("doctype")
            name = kwargs.get("name")
        if name is None:
            return self._frappe.get_doc(kwargs)
        return self._frappe.get_doc(doctype, name)

    def exists(self, doctype, name_or_filters):
        return self._frappe.db.exists(doctype, name_or_filters)

    def set_value(self, doctype, name_or_filters, field, value=None):
        if value is None and isinstance(field, dict) and not isinstance(name_or_filters, dict):
            return self._frappe.db.set_value(doctype, name_or_filters, field)
        return self._frappe.db.set_value(doctype, name_or_filters, field, value)

    def get_single_value(self, doctype, field):
        return self._frappe.db.get_single_value(doctype, field)

    def commit(self):
        self._frappe.db.commit()

    def insert_child(self, child_doctype, parent, row):
        raise NotImplementedError("usar get_doc + append en modo real")

    def count(self, doctype, filters=None):
        return self._frappe.db.count(doctype, filters)

    def delete_doc(self, doctype, name):
        return self._frappe.delete_doc(doctype, name, ignore_permissions=True,
                                       force=True)


class _MemRow(object):

    def __init__(self):
        self._fields = {}

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self._fields[key] = value

    def __getattr__(self, key):
        if key.startswith("_"):
            raise AttributeError(key)
        return self._fields.get(key)

    def get(self, key, default=None):
        return self._fields.get(key, default)


class MemDoc(_MemRow):

    def __init__(self, store, doctype, name=None, row=None):
        _MemRow.__init__(self)
        self._store = store
        self._doctype = doctype
        self._name = name
        self._pending_childs = {}
        if row is None and name is not None:
            row = store.get(doctype, name) or {}
        self._fields = dict(row or {})
        if name is not None:
            self._fields["name"] = name

    def __getattr__(self, key):
        if key in ("name", "nvfac_esta", "nvfac_ueve", "nvfac_conv",
                   "qp_reject_orig_state", "qp_motive", "qp_is_event_completed",
                   "qp_auto_reject_rule", "qp_reject_retry_enabled",
                   "qp_reject_is_invoice_error", "nvfac_nume", "nvpro_ndoc",
                   "nvfac_cont"):
            return self._fields.get(key, None)
        return _MemRow.__getattr__(self, key)

    def append(self, child_doctype, data=None):
        row = _MemRow()
        if data:
            for key, value in (data or {}).items():
                row.__setattr__(key, value)
        self._pending_childs.setdefault(child_doctype, []).append(row)
        return row

    def save(self):
        if not self._name:
            self._name = self._fields.get("name")
        if not self._name:
            self._name = "{}-{}".format(self._doctype, 1)
            self._fields["name"] = self._name
        self._fields["name"] = self._name
        if self._store.exists(self._doctype, self._name):
            self._store.update(self._doctype, self._name, self._fields)
        else:
            self._store.insert(self._doctype, self._fields, name=self._name)
        for child_doctype, rows in self._pending_childs.items():
            for row in rows:
                data = dict(row._fields)
                data["parent"] = self._name
                self._store.insert(child_doctype, data)

    @property
    def _doc_name(self):
        return self._name


class _Memory(object):
    """Implementacion in-memory: todos los doctypes se leen del store (los que
    no estan sembrados devuelven vacio). Sin acceso a la DB real."""

    def __init__(self, store, frappe=None):
        self._store = store

    def get_all(self, doctype, filters=None, fields=None, order_by=None,
                limit=None, start=0, page_length=None, pluck=None,
                sort_field=None):
        return self._store.query(
            doctype, filters=filters, fields=fields, order_by=order_by,
            start=start, page_length=page_length, pluck=pluck, limit=limit)

    def get_list(self, doctype, filters=None, fields=None, order_by=None,
                 start=0, page_length=None, pluck=None):
        fields = fields or ["*"]
        return self._store.query(
            doctype, filters=filters, fields=fields, order_by=order_by,
            start=start, page_length=page_length, pluck=pluck)

    def get_value(self, doctype, name_or_filters, field=None):
        return self._store.get_value(doctype, name_or_filters, field)

    def get_doc(self, doctype, name=None, **kwargs):
        if isinstance(doctype, dict):
            kwargs = doctype
            doctype = kwargs.get("doctype")
            name = kwargs.get("name")
        if name is None:
            return MemDoc(self._store, kwargs.get("doctype"), row=kwargs)
        return MemDoc(self._store, doctype, name=name)

    def exists(self, doctype, name_or_filters):
        return self._store.exists(doctype, name_or_filters)

    def set_value(self, doctype, name_or_filters, field, value=None):
        if value is None and isinstance(field, dict):
            for key, val in field.items():
                self._store.set_value(doctype, name_or_filters, key, val)
            return True
        return self._store.set_value(doctype, name_or_filters, field, value)

    def get_single_value(self, doctype, field):
        if self._store.has_doctype(doctype):
            rows = self._store.query(doctype)
            if rows:
                return rows[0].get(field)
        return None

    def commit(self):
        pass

    def insert_child(self, child_doctype, parent, row):
        data = dict(row)
        data["parent"] = parent
        self._store.insert(child_doctype, data)

    def count(self, doctype, filters=None):
        return self._store.count(doctype, filters)

    def delete_doc(self, doctype, name):
        self._store.delete(doctype, name)


class DataFacade(object):

    def __init__(self, store=None, frappe=None):
        self._store = store
        import frappe as actual_frappe
        self._frappe = frappe or actual_frappe
        self._impl = _Memory(store, self._frappe) if store is not None else _Real(self._frappe)

    @property
    def is_in_memory(self):
        return self._store is not None

    def get_all(self, *args, **kwargs):
        return self._impl.get_all(*args, **kwargs)

    def get_list(self, *args, **kwargs):
        return self._impl.get_list(*args, **kwargs)

    def get_value(self, *args, **kwargs):
        return self._impl.get_value(*args, **kwargs)

    def get_doc(self, *args, **kwargs):
        return self._impl.get_doc(*args, **kwargs)

    def exists(self, *args, **kwargs):
        return self._impl.exists(*args, **kwargs)

    def set_value(self, *args, **kwargs):
        return self._impl.set_value(*args, **kwargs)

    def get_single_value(self, *args, **kwargs):
        return self._impl.get_single_value(*args, **kwargs)

    def commit(self):
        return self._impl.commit()

    def insert_child(self, *args, **kwargs):
        return self._impl.insert_child(*args, **kwargs)

    def count(self, *args, **kwargs):
        return self._impl.count(*args, **kwargs)

    def delete_doc(self, *args, **kwargs):
        return self._impl.delete_doc(*args, **kwargs)

    @property
    def db(self):
        return self