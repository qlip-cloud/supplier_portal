import frappe
import zipfile
from io import BytesIO

from qp_supplier_front.uses_cases.documenteme.attachments import (
    download_files,
    ensure_extension,
)


def _get_content(attached_row):
    """Contenido del File resuelto por file_id o, si falta, por file_url."""
    file_id = str(attached_row.get("file_id") or "").strip()
    if not file_id:
        file_url = str(attached_row.get("file_url") or "").strip()
        if file_url:
            file_id = frappe.db.get_value(
                "File", {"file_url": file_url}, "name"
            ) or ""
    if not file_id:
        return None
    return frappe.get_doc("File", file_id).get_content()


def _no_documents(invoice_number):
    frappe.local.response.filename = "{}.txt".format(invoice_number)
    frappe.local.response.filecontent = "No hay documentos disponibles para descargar."
    frappe.local.response.type = "download"


@frappe.whitelist()
def files(doc_name, invoice_number):
    try:
        attached_files = frappe.get_all(
            "qp_SP_DocumentAttach",
            filters={"parent": doc_name, "parenttype": "qp_SP_DocumentDetail"},
            fields=["file_name", "file_type", "file_url", "file_id"]
        )

        entries = download_files(attached_files)

        zip_buffer = BytesIO()
        written = 0
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for attached_row in entries:
                try:
                    content = _get_content(attached_row)
                    if content is None:
                        continue
                    file_name = ensure_extension(
                        attached_row.get("file_name"),
                        attached_row.get("file_type"),
                    )
                    zf.writestr(file_name, content)
                    written += 1
                except Exception:
                    pass

        if not written:
            _no_documents(invoice_number)
            return

        zip_buffer.seek(0)

        frappe.local.response.filename = "{}.zip".format(invoice_number)
        frappe.local.response.filecontent = zip_buffer.getvalue()
        frappe.local.response.type = "download"

    except Exception as error:
        frappe.local.response.filename = "error.txt"
        frappe.local.response.filecontent = "Error al generar descarga: {}".format(str(error))
        frappe.local.response.type = "download"
