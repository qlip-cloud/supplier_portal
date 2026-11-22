from datetime import date, datetime

INPUT_FORMAT = "%Y-%m-%d"
OUTPUT_FORMAT = "%d/%m/%Y"
MAX_RANGE_DAYS = 90


def _parse_date(value):
    """Convierte un Date de Frappe (YYYY-MM-DD) o un date a date.

    Retorna None si el valor esta vacio o no tiene el formato esperado.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), INPUT_FORMAT).date()
    except (TypeError, ValueError):
        return None


def _error(message):
    return {
        "ok": False,
        "error": message,
        "nvfac_fini": None,
        "nvfac_ffin": None,
    }


def validate_date_range(start_date, end_date, today=None,
                        max_days=MAX_RANGE_DAYS):
    """Valida un rango de sincronizacion manual de documenteme.

    Reglas:
      - Ambas fechas son obligatorias y con formato YYYY-MM-DD.
      - La fecha de inicio no puede ser mayor que la de fin.
      - La fecha de fin no puede superar el dia actual.
      - El rango inclusivo no puede superar `max_days` (90 por defecto).

    Retorna un dict con `ok`, `error` y las fechas en formato documenteme
    (`dd/mm/YYYY`) cuando el rango es valido.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    if not start_date or not end_date:
        return _error("Debe indicar la fecha de inicio y la fecha de fin")
    if start is None or end is None:
        return _error("Formato de fecha inválido, use AAAA-MM-DD")
    if start > end:
        return _error("La fecha de inicio no puede ser mayor que la fecha de fin")

    today = today or date.today()
    if end > today:
        return _error("La fecha de fin no puede ser mayor que hoy")
    if (end - start).days + 1 > max_days:
        return _error(
            "El rango de fechas no puede superar los {} días".format(max_days))

    return {
        "ok": True,
        "error": None,
        "nvfac_fini": start.strftime(OUTPUT_FORMAT),
        "nvfac_ffin": end.strftime(OUTPUT_FORMAT),
    }
