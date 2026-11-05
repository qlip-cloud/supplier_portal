import frappe
import zipfile
from io import BytesIO


@frappe.whitelist()
def files(doc_name, invoice_number):
    try:
        attached_files = frappe.get_all(
            "qp_SP_DocumentAttach",
            filters={"parent": doc_name, "parenttype": "qp_SP_DocumentDetail"},
            fields=["file_name", "file_type", "file_id"]
        )

        non_xml_files = [
            f for f in attached_files
            if f.get("file_type", "").upper() != "XML"
        ]

        if not non_xml_files:
            frappe.local.response.filename = "{}.txt".format(invoice_number)
            frappe.local.response.filecontent = "No hay documentos disponibles para descargar."
            frappe.local.response.type = "download"
            return

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in non_xml_files:
                try:
                    file_doc = frappe.get_doc("File", f.get("file_id"))
                    content = file_doc.get_content()
                    file_name = f.get("file_name") or "documento"
                    zf.writestr(file_name, content)
                except Exception:
                    pass

        zip_buffer.seek(0)

        frappe.local.response.filename = "{}.zip".format(invoice_number)
        frappe.local.response.filecontent = zip_buffer.getvalue()
        frappe.local.response.type = "download"

    except Exception as error:
        frappe.local.response.filename = "error.txt"
        frappe.local.response.filecontent = "Error al generar descarga: {}".format(str(error))
        frappe.local.response.type = "download"
