"""Log en archivo de requests de API que crean Purchase Order / Purchase Receipt.

Un archivo por doctype, JSON por linea:

* ``logs/inbound_purchase_order.log``
* ``logs/inbound_purchase_receipt.log``

(en el ``logs/`` del bench y en ``sites/<sitio>/logs/``, con rotacion de
10 MB y 10 backups).

Se registran dos eventos:

* ``created``: via doc_events ``after_insert`` (``log_inbound_api_request``).
* ``failed``: via los controllers override (``log_failed_api_request``), que
  capturan errores como ``LinkValidationError`` en ``_validate_links`` (ocurre
  antes de ``after_insert``) y re-lanzan la excepcion.

Solo se registran requests HTTP bajo ``/api/``. El campo ``origin`` distingue
``api`` (cliente externo) de ``desk`` (AJAX interno, que manda
``X-Frappe-CSRF-Token``).

El logging nunca rompe la creacion del documento: cualquier error se traga.
"""

import json
import logging
import os
import traceback
from logging.handlers import RotatingFileHandler

API_PREFIX = "/api/"

LOG_MODULES = {
    "Purchase Order": "inbound_purchase_order",
    "Purchase Receipt": "inbound_purchase_receipt",
}
DEFAULT_LOG_MODULE = "inbound_api"
ERROR_LOGGER = "inbound_api_errors"

LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUPS = 10

_file_loggers = {}


def is_api_request(path):
    """True para requests HTTP servidas bajo /api/."""
    return bool(path) and str(path).startswith(API_PREFIX)


def build_log_record(doctype, response, name=None, supplier=None, path=None,
                     raw_body=None, status_code=None, event="created",
                     origin="api", user=None, ip=None, method=None):
    """Arma el registro que se serializa como una linea JSON."""
    return {
        "event": event,
        "doctype": doctype,
        "name": name or None,
        "supplier": supplier or None,
        "status_code": status_code,
        "origin": origin,
        "user": user,
        "ip": ip,
        "method": method,
        "path": path,
        "payload": raw_body,
        "response": response,
    }


def log_inbound_api_request(doc, method=None):
    """doc_events ``after_insert``: registra la creacion hecha por API."""
    try:
        request = _get_request()
        if request is None:
            return

        path = getattr(request, "path", None)
        if not is_api_request(path):
            return

        record = build_log_record(
            doctype=doc.doctype,
            name=doc.name,
            response=doc.as_dict(),
            supplier=doc.get("supplier"),
            path=path,
            raw_body=_get_raw_body(request),
            status_code=_response_status_code(),
            event="created",
            **_request_meta(request)
        )
        _write(record)
    except Exception:
        _log_failure()


def log_failed_api_request(doc, error):
    """Registra un request de API que fallo durante el insert.

    Se invoca desde los controllers override (Purchase Order / Purchase
    Receipt). El error original se re-lanza desde ahi.
    """
    try:
        request = _get_request()
        if request is None:
            return

        path = getattr(request, "path", None)
        if not is_api_request(path):
            return

        record = build_log_record(
            doctype=doc.doctype,
            name=doc.name,
            response={
                "exc_type": type(error).__name__,
                "message": str(error),
            },
            supplier=doc.get("supplier"),
            path=path,
            raw_body=_get_raw_body(request),
            status_code=_error_status_code(error),
            event="failed",
            **_request_meta(request)
        )
        _write(record)
    except Exception:
        _log_failure()


def _write(record):
    module = LOG_MODULES.get(record.get("doctype"), DEFAULT_LOG_MODULE)
    line = json.dumps(record, default=str, ensure_ascii=False)
    _emit(module, line)


def _emit(module, line):
    _get_file_logger(module).info(line)


def _get_file_logger(module):
    """Logger con rotacion a ``<bench>/logs`` y ``sites/<sitio>/logs``.

    No usa ``frappe.logger`` porque ese handler resuelve ``../logs`` relativo
    al cwd; aca armamos la ruta absoluta desde ``get_bench_path``/sitio.
    """
    logger = _file_loggers.get(module)
    if logger is not None:
        return logger

    import frappe

    logger = logging.getLogger("qp_inbound_api.{0}".format(module))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s {0} %(message)s".format(module)
    )

    for path in _log_paths(frappe, module):
        try:
            directory = os.path.dirname(path)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            handler = RotatingFileHandler(
                path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUPS,
                encoding="utf-8",
            )
        except Exception:
            continue
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _file_loggers[module] = logger
    return logger


def _log_paths(frappe, module):
    filename = "{0}.log".format(module)
    paths = []
    try:
        paths.append(
            os.path.join(frappe.utils.get_bench_path(), "logs", filename)
        )
    except Exception:
        pass
    try:
        paths.append(frappe.get_site_path("logs", filename))
    except Exception:
        pass
    return paths


def _request_meta(request):
    import frappe

    headers = getattr(request, "headers", None)
    has_csrf = bool(headers and headers.get("X-Frappe-CSRF-Token"))
    return {
        "origin": "desk" if has_csrf else "api",
        "user": _safe_session_user(frappe),
        "ip": (
            getattr(frappe.local, "request_ip", None)
            or getattr(request, "remote_addr", None)
        ),
        "method": getattr(request, "method", None),
    }


def _safe_session_user(frappe):
    try:
        return frappe.session.user
    except Exception:
        return None


def _get_request():
    import frappe

    return getattr(frappe.local, "request", None)


def _response_status_code():
    """HTTP status que Frappe devolvera al cliente (200 por defecto)."""
    import frappe

    response = getattr(frappe.local, "response", None)
    if not response:
        return 200
    try:
        return int(response.get("http_status_code") or 200)
    except Exception:
        return 200


def _error_status_code(error):
    try:
        return int(getattr(error, "http_status_code", 500) or 500)
    except Exception:
        return 500


def _get_raw_body(request):
    try:
        return request.get_data(as_text=True)
    except Exception:
        return None


def _log_failure():
    try:
        _get_file_logger(ERROR_LOGGER).error(
            "No se pudo escribir el log de requests de API entrantes\n{0}".format(
                traceback.format_exc()
            )
        )
    except Exception:
        pass
