# -*- coding: utf-8 -*-
"""
test_sync_window.py
====================
Pruebas unitarias para services/sync_window.py (ventanas de sincronizacion).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_sync_window -v
"""
import unittest
from datetime import datetime

from qp_supplier_front.services.sync_window import (
    generate_date_windows,
    compute_sync_start,
    today_start,
    HISTORICAL_START_DATE,
)


class TestGenerateDateWindows(unittest.TestCase):

    def test_span_shorter_than_window_returns_single_window(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 10)
        windows = list(generate_date_windows(start, end, window_days=30))
        self.assertEqual(windows, [(start, end)])

    def test_span_exactly_one_window(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        windows = list(generate_date_windows(start, end, window_days=30))
        self.assertEqual(windows, [(start, end)])

    def test_multiple_windows_cover_full_span(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 1)
        windows = list(generate_date_windows(start, end, window_days=30))
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0][0], start)
        self.assertEqual(windows[-1][1], end)
        for w_start, w_end in windows:
            self.assertLess(w_start, w_end)
            self.assertLessEqual(w_end, end)

    def test_windows_are_contiguous(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 6, 1)
        windows = list(generate_date_windows(start, end, window_days=30))
        for (w_end_prev, (w_start_next, _)) in zip(windows, windows[1:]):
            self.assertEqual(w_end_prev[1], w_start_next)

    def test_last_window_is_trimmed_to_end(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 15)
        windows = list(generate_date_windows(start, end, window_days=30))
        self.assertEqual(windows[-1][1], end)

    def test_invalid_window_days_raises(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 2, 1)
        with self.assertRaises(ValueError):
            list(generate_date_windows(start, end, window_days=0))

    def test_default_window_days_constant(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)
        windows = list(generate_date_windows(start, end))
        self.assertEqual(windows, [(start, end)])


class TestComputeSyncStart(unittest.TestCase):

    def test_no_last_date_uses_historical_start(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        start = compute_sync_start(None, today)
        self.assertEqual(start, HISTORICAL_START_DATE)

    def test_last_date_in_past_is_kept(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        last_date = datetime(2026, 7, 1, 8, 30, 0)
        start = compute_sync_start(last_date, today)
        self.assertEqual(start, last_date)

    def test_last_date_as_date_object_is_normalized(self):
        from datetime import date
        today = datetime(2026, 8, 6, 12, 0, 0)
        last_date = date(2026, 7, 1)
        start = compute_sync_start(last_date, today)
        self.assertEqual(start, datetime(2026, 7, 1, 0, 0, 0))

    def test_last_date_as_string_datetime_is_parsed(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        start = compute_sync_start("2026-07-01 00:00:00", today)
        self.assertEqual(start, datetime(2026, 7, 1, 0, 0, 0))

    def test_last_date_as_string_with_microseconds_is_parsed(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        start = compute_sync_start("2026-07-01 00:00:00.000000", today)
        self.assertEqual(start, datetime(2026, 7, 1, 0, 0, 0))

    def test_last_date_as_string_date_is_parsed(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        start = compute_sync_start("2026-07-01", today)
        self.assertEqual(start, datetime(2026, 7, 1, 0, 0, 0))

    def test_last_date_as_string_today_syncs_only_today(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        start = compute_sync_start("2026-08-06 09:00:00", today)
        self.assertEqual(start, today_start(today))

    def test_last_date_today_syncs_only_today(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        last_date = datetime(2026, 8, 6, 9, 0, 0)
        start = compute_sync_start(last_date, today)
        self.assertEqual(start, today_start(today))
        self.assertEqual(start.hour, 0)
        self.assertEqual(start.minute, 0)

    def test_last_date_future_syncs_only_today(self):
        today = datetime(2026, 8, 6, 12, 0, 0)
        last_date = datetime(2026, 8, 10, 9, 0, 0)
        start = compute_sync_start(last_date, today)
        self.assertEqual(start, today_start(today))


class TestTodayStart(unittest.TestCase):

    def test_returns_midnight(self):
        today = datetime(2026, 8, 6, 23, 59, 59)
        start = today_start(today)
        self.assertEqual((start.hour, start.minute, start.second), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
