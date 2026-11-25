# -*- coding: utf-8 -*-
"""
test_invoice_attachments.py
===========================
Pruebas del nucleo puro de adjuntos de facturas documenteme
(uses_cases/documenteme/attachments.py).

Sin base de datos: solo funciones puras.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_invoice_attachments.py -v
"""

import unittest

from qp_supplier_front.uses_cases.documenteme.attachments import (
    build_attachment_row,
    count_non_xml,
    find_attachment,
    guess_file_type,
    has_downloadable,
    is_downloadable_type,
    plan_attachment,
)


class TestGuessFileType(unittest.TestCase):

    def test_extension_mayusculas(self):
        self.assertEqual(guess_file_type("factura.PDF"), "PDF")

    def test_extension_con_puntos(self):
        self.assertEqual(guess_file_type("ad.900.xml"), "XML")

    def test_sin_extension(self):
        self.assertEqual(guess_file_type("FE333"), "")

    def test_ignora_query_string(self):
        self.assertEqual(guess_file_type("factura.pdf?token=1"), "PDF")

    def test_vacio(self):
        self.assertEqual(guess_file_type(None), "")


class TestIsDownloadableType(unittest.TestCase):

    def test_xml_no_descargable(self):
        self.assertFalse(is_downloadable_type("XML"))
        self.assertFalse(is_downloadable_type("xml"))

    def test_pdf_descargable(self):
        self.assertTrue(is_downloadable_type("PDF"))

    def test_sin_tipo_descargable(self):
        self.assertTrue(is_downloadable_type(""))


class TestCountNonXml(unittest.TestCase):

    def test_cuenta_solo_no_xml(self):
        rows = [
            {"file_type": "XML"},
            {"file_type": "pdf"},
            {"file_type": ""},
        ]
        self.assertEqual(count_non_xml(rows), 2)

    def test_solo_xml(self):
        self.assertEqual(count_non_xml([{"file_type": "XML"}]), 0)

    def test_vacio(self):
        self.assertEqual(count_non_xml(None), 0)


class TestHasDownloadable(unittest.TestCase):

    def test_sin_adjuntos(self):
        self.assertFalse(has_downloadable([]))

    def test_solo_xml_no_cuenta_aunque_exista(self):
        rows = [{"file_type": "XML", "file_id": "f1"}]
        self.assertFalse(has_downloadable(rows, exists_fn=lambda row: True))

    def test_pdf_existente_cuenta(self):
        rows = [{"file_type": "PDF", "file_id": "f1"}]
        self.assertTrue(has_downloadable(rows, exists_fn=lambda row: True))

    def test_pdf_sin_archivo_fisico_no_cuenta(self):
        rows = [{"file_type": "PDF", "file_id": "f1"}]
        self.assertFalse(has_downloadable(rows, exists_fn=lambda row: False))

    def test_pdf_con_archivo_fisico_cuenta(self):
        rows = [
            {"file_type": "XML", "file_id": "f0"},
            {"file_type": "PDF", "file_id": "f1"},
        ]

        def exists(row):
            return row.get("file_id") == "f1"

        self.assertTrue(has_downloadable(rows, exists_fn=exists))


class TestFindAttachment(unittest.TestCase):

    def test_encuentra_por_file_id(self):
        rows = [{"file_id": "a"}, {"file_id": "b"}]
        self.assertEqual(find_attachment(rows, file_id="b"), rows[1])

    def test_encuentra_por_file_url(self):
        rows = [{"file_url": "/files/a.pdf"}, {"file_url": "/files/b.pdf"}]
        self.assertEqual(
            find_attachment(rows, file_url="/files/b.pdf"), rows[1]
        )

    def test_no_encuentra(self):
        self.assertIsNone(find_attachment([{"file_id": "a"}], file_id="z"))
        self.assertIsNone(find_attachment(None, file_id="z"))


class TestBuildAttachmentRow(unittest.TestCase):

    def test_deriva_tipo_desde_extension(self):
        row = build_attachment_row("factura.PDF", "/files/factura.pdf", "f1")
        self.assertEqual(row["file_name"], "factura.PDF")
        self.assertEqual(row["file_type"], "PDF")
        self.assertEqual(row["file_url"], "/files/factura.pdf")
        self.assertEqual(row["file_id"], "f1")

    def test_usa_basename_si_falta_nombre(self):
        row = build_attachment_row("", "/files/factura.pdf?x=1", "f1")
        self.assertEqual(row["file_name"], "factura.pdf")
        self.assertEqual(row["file_type"], "PDF")

    def test_nombre_default(self):
        row = build_attachment_row("", "", "f1")
        self.assertEqual(row["file_name"], "documento")


class TestPlanAttachment(unittest.TestCase):

    def test_agrega_cuando_no_existe(self):
        row = build_attachment_row("f.pdf", "/files/f.pdf", "f1")
        to_add, existing = plan_attachment([], row)
        self.assertEqual(to_add, row)
        self.assertIsNone(existing)

    def test_no_duplica_por_file_id(self):
        current = [{"file_id": "f1", "file_url": "/files/f.pdf"}]
        row = build_attachment_row("f.pdf", "/files/f.pdf", "f1")
        to_add, existing = plan_attachment(current, row)
        self.assertIsNone(to_add)
        self.assertEqual(existing, current[0])

    def test_no_duplica_por_url(self):
        current = [{"file_id": "", "file_url": "/files/f.pdf"}]
        row = build_attachment_row("f.pdf", "/files/f.pdf", "f2")
        to_add, existing = plan_attachment(current, row)
        self.assertIsNone(to_add)
        self.assertEqual(existing, current[0])


if __name__ == "__main__":
    unittest.main()


class TestDownloadFiles(unittest.TestCase):

    def test_incluye_xml_y_no_xml(self):
        from qp_supplier_front.uses_cases.documenteme.attachments import (
            download_files,
        )

        rows = [
            {"file_type": "XML", "file_id": "f1", "file_name": "a"},
            {"file_type": "PDF", "file_id": "f2", "file_name": "b.pdf"},
        ]
        self.assertEqual(len(download_files(rows)), 2)

    def test_excluye_filas_sin_referencia(self):
        from qp_supplier_front.uses_cases.documenteme.attachments import (
            download_files,
        )

        self.assertEqual(download_files([{"file_name": "x"}]), [])

    def test_acepta_file_url_sin_file_id(self):
        from qp_supplier_front.uses_cases.documenteme.attachments import (
            download_files,
        )

        rows = [{"file_type": "PDF", "file_url": "/files/a.pdf"}]
        self.assertEqual(len(download_files(rows)), 1)


class TestEnsureExtension(unittest.TestCase):

    def test_agrega_extension_segun_tipo(self):
        from qp_supplier_front.uses_cases.documenteme.attachments import (
            ensure_extension,
        )

        self.assertEqual(ensure_extension("FE333", "XML"), "FE333.xml")

    def test_respeta_extension_existente(self):
        from qp_supplier_front.uses_cases.documenteme.attachments import (
            ensure_extension,
        )

        self.assertEqual(ensure_extension("a.pdf", "PDF"), "a.pdf")

    def test_sin_tipo_no_agrega(self):
        from qp_supplier_front.uses_cases.documenteme.attachments import (
            ensure_extension,
        )

        self.assertEqual(ensure_extension("a", ""), "a")
        self.assertEqual(ensure_extension("", ""), "documento")
