"""
sync_window.py
================
Utilidades puras para la sincronizacion fraccionada por ventanas de fechas.
Usadas por ordenes y recibos para hacer catch-up historico sin depender
de endpoints sin filtros (ORDER_ALL / PAYMENT_ALL).

- HISTORICAL_START_DATE: fecha de inicio del catch-up (configurada).
- FULL_SYNC_WINDOW_DAYS: ancho de cada ventana en dias.
"""

from datetime import date, datetime, timedelta

HISTORICAL_START_DATE = datetime(2024, 1, 1)
FULL_SYNC_WINDOW_DAYS = 30


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        return _parse_datetime(value)
    return value


def _parse_datetime(value):
    text = value.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return value


def generate_date_windows(start, end, window_days=FULL_SYNC_WINDOW_DAYS):
    """
    Genera pares (w_start, w_end) que cubren [start, end) en ventanas
    de window_days dias. La ultima ventana se recorta a end.
    """
    if window_days <= 0:
        raise ValueError("window_days debe ser mayor a 0")

    cursor = start

    while cursor < end:
        win_end = cursor + timedelta(days=window_days)
        if win_end > end:
            win_end = end
        yield cursor, win_end
        cursor = win_end


def compute_sync_start(last_date, today, historical_start=HISTORICAL_START_DATE):
    """
    Calcula la fecha de inicio de la sincronizacion:
      - Sin datos previos: historical_start.
      - Con ultima fecha de dias pasados: desde esa fecha en adelante.
      - Si la ultima fecha es hoy: solo se sincroniza el dia actual.
    """
    if last_date is None:
        return historical_start

    last_date = _as_datetime(last_date)

    if last_date.date() >= today.date():
        return today.replace(hour=0, minute=0, second=0, microsecond=0)

    return last_date


def today_start(today):
    return today.replace(hour=0, minute=0, second=0, microsecond=0)
