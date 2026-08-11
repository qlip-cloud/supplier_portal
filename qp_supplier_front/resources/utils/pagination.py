import frappe
import json
from qp_supplier_front.services.pagination import get_paginated, get_paginated_filtered, get_detail
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.enrich_document_detail import enrich_document_detail

@frappe.whitelist()
def render_pagination(page, key, doctype, supplier_id, doctype_detail, order_by, filters = {}):
    try:
        
        msg = "Los datos han sido paginados correctamente"
        
        parsed_filters = json.loads(filters) if filters else {}
        
        if doctype == "qp_SP_DocumentDetail":
            base_filters = {}
            base_filters.update(parsed_filters)
            base_filters["nvfac_ueve"] = ["is", "not set"]
            pagination = get_paginated_filtered(int(page), doctype, order_by, base_filters)

            for doc in pagination:
                doc["detail_lines"] = frappe.get_all(
                    "qp_SP_DetailLine",
                    filters={"parent": doc.name, "parenttype": doctype},
                    fields=["nvpro_codi", "nvuni_desc", "nvdet_tcan", "nvdet_valo", "nvdet_vdes", "nvdet_stot"]
                )
                allowance_charges = frappe.get_all(
                    "qp_SP_AllowanceCharge",
                    filters={"parent": doc.name, "parenttype": doctype},
                    fields=["reason", "amount", "charge_indicator"]
                )
                doc["allowance_charges"] = []
                base_total = sum(dl["nvdet_stot"] or 0 for dl in doc["detail_lines"])
                running_total = base_total
                for ac in allowance_charges:
                    if not ac.get("amount"):
                        continue
                    signed_amount = ac["amount"] if ac.get("charge_indicator") else -ac["amount"]
                    running_total += signed_amount
                    doc["allowance_charges"].append({
                        "reason": ac.get("reason") or "Descuento/Cargo",
                        "signed_amount": signed_amount,
                        "running_total": running_total
                    })
                doc["attached_files"] = frappe.get_all(
                    "qp_SP_DocumentAttach",
                    filters={"parent": doc.name, "parenttype": doctype},
                    fields=["file_name", "file_type", "file_url", "file_id"]
                )
                doc["non_xml_count"] = len(
                    [f for f in doc["attached_files"] if f.get("file_type", "").upper() != "XML"]
                )
                assignee_id = frappe.db.get_value(
                    "qp_SP_DocumentSyncLine", doc.get("nvfac_nume"), "assigned_to"
                )
                assigned_user_ids = [
                    row.get("user")
                    for row in frappe.get_all(
                        "qp_SP_SyncLineAssignedUser",
                        filters={"parent": doc.get("nvfac_nume"), "parenttype": "qp_SP_DocumentSyncLine"},
                        fields=["user"]
                    )
                ]
                if not assigned_user_ids and assignee_id:
                    assigned_user_ids = [assignee_id]
                doc["assigned_to_id"] = assignee_id
                doc["assigned_to_ids"] = assigned_user_ids
                if assigned_user_ids:
                    names = []
                    for user_id in assigned_user_ids:
                        names.append(frappe.db.get_value("User", user_id, "full_name") or user_id)
                    doc["assigned_to_name"] = "Asignado a:\n" + "\n".join("- " + name for name in names)
                else:
                    doc["assigned_to_name"] = None
                enrich_document_detail(doc)
        else:
            pagination = get_paginated(int(page), doctype, supplier_id, order_by, parsed_filters)
            frappe.enqueue(f"qp_supplier_front.uses_cases.{key}.sync_by_supplier.handler", supplier_id=supplier_id, queue='long', is_async=True, timeout=14400, job_name=f"send sync {doctype} {supplier_id}")

        template = frappe.render_template(f"qp_supplier_front/templates/list/{key}/list.html", {
                    key: pagination, "doctype_detail":doctype_detail, "key": key, "doctype": doctype
                })
        
        response(200,  msg, template)
        
    except Exception as error:
        
        msg = f"Error al paginar {doctype} para {supplier_id}: {str(error)}"
        
        response(500,  msg)
        
@frappe.whitelist()
def render_detail(key, parent_doctype, doctype, name, page = 0):
    
    try:
        
        msg = "Los datos han sido creados correctamente"
        
        detail = get_detail(parent_doctype, doctype, name, int(page))
        
        template = frappe.render_template(f"qp_supplier_front/templates/list/{key}/list_detail.html", detail)
            
        response(200,  msg, template)
        
    except Exception as error:
        
        msg = f"Error al buscar {doctype} para {name}: {str(error)}"
        
        response(500,  msg)