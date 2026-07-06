import frappe
import json
from qp_supplier_front.services.pagination import get_paginated, get_paginated_filtered, get_detail
from qp_supplier_front.resources.response import handler as response

@frappe.whitelist()
def render_pagination(page, key, doctype, supplier_id, doctype_detail, order_by, filters = {}):
    try:
        
        msg = "Los datos han sido paginados correctamente"
        
        parsed_filters = json.loads(filters) if filters else {}
        
        if doctype == "qp_SP_DocumentDetail":
            pagination = get_paginated_filtered(int(page), doctype, order_by, parsed_filters)

            for doc in pagination:
                doc["detail_lines"] = frappe.get_all(
                    "qp_SP_DetailLine",
                    filters={"parent": doc.name, "parenttype": doctype},
                    fields=["nvpro_codi", "nvuni_desc", "nvdet_tcan", "nvdet_valo", "nvdet_stot"]
                )
                doc["factura_interna"] = ""
                doc["ordenes_compra"] = []
                doc["recepciones"] = []
                doc["productos_orden_compra"] = []
                doc["productos_recepcion"] = []
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