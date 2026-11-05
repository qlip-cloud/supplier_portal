import frappe
from frappe import parse_json
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.documenteme.assign import assign_documents


@frappe.whitelist()
def get_users():
    try:
        users_data = frappe.get_all(
            "User",
            filters={"enabled": 1},
            fields=["name", "first_name", "last_name"]
        )

        response(200, data=users_data, msg="")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener usuarios: {}".format(str(error)))


@frappe.whitelist()
def get_document_data(doc_names):
    try:
        doc_names_list = parse_json(doc_names)

        data = frappe.get_all(
            "qp_SP_DocumentDetail",
            filters={"name": ["in", doc_names_list]},
            fields=["name", "nvfac_nume", "nvfac_orde", "nvfac_rece"]
        )

        response(200, data=data, msg="")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener datos de documentos: {}".format(str(error)))


@frappe.whitelist()
def assign(doc_names, user):
    try:
        doc_names_list = parse_json(doc_names)

        sync_line_names = []
        for doc_name in doc_names_list:
            sync_line = frappe.db.get_value(
                "qp_SP_DocumentDetail",
                doc_name,
                "document_sync_line"
            )
            if sync_line:
                sync_line_names.append(sync_line)

        if not sync_line_names:
            response(400, "No se encontraron lineas de sincronizacion para los documentos seleccionados")
            return

        assign_documents(
            sync_line_names,
            user,
            get_doc_fn=frappe.get_doc,
            save_fn=lambda doc: doc.save(),
        )

        frappe.db.commit()

        response(200, "Asignacion exitosa")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al asignar: {}".format(str(error)))
