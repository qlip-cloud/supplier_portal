import frappe
from datetime import datetime
from qp_supplier_front.util.command import create_doc
from qp_supplier_front.services.sync_doc import setup_doc, get_last_creation, get_result
from qp_supplier_front.constant.endpoint import DISPATH_SUPPLIER_ID, INVOICE_SUPPLIER_DATE_RANGE, INVOICE_ALL
from qp_authorization.use_case.bearer.authorize import send_request


request_key = "Bols"
request_key_id = "TravelId"
doctype = "qp_SP_Dispatch"
doctype_key = "travel_id"
request_list_key = None
request_list_key_id = None
doctype_list_key = None
doctype_list = None
doctype_list_key_id = None
is_validate_items = False
order_by = "create_date"

endpoint = {
    "all": DISPATH_SUPPLIER_ID,
    "range": INVOICE_SUPPLIER_DATE_RANGE
}
@frappe.whitelist() 
def handler(supplier_id):

    
    #result = get_result(endpoint, supplier_id, latest_record)
    result = get_result(endpoint, supplier_id)

    sync_dispatch_fast(result, supplier_id)

    move_to_final_dispatch()
    frappe.db.commit()
    
@frappe.whitelist() 
def handler_all():
    
    result = send_request(INVOICE_ALL)

    setup_doc(result, request_key, request_key_id, request_list_key, request_list_key_id ,doctype, doctype_key, doctype_list_key, doctype_list,doctype_list_key_id, is_validate_items, get_doc_base, insert_doc)
    
def sync_dispatch_fast(json_data, supplier_id):
    
    bols = json_data.get("Bols", [])
    
    if not bols:
    
        return 0
    
    frappe.db.sql(f"DELETE FROM `tabqp_SP_DispatchSync` where supplier_id = '{supplier_id}'")

    now = frappe.utils.now()
    values = []
    rows = []
    for b in bols:
        row = str((
            b.get("Bol"),
            b.get("TravelId"),
            b.get("LicensePlate"),
            b.get("Bol"),
            b.get("Origin"),
            b.get("Destination"),
            b.get("BolValue") or 0,
            supplier_id,
            now,
            now,
            'Administrator',
            'Administrator',
            0
        ))
        rows.append(row)
    print(rows)    
    values_query = ", ".join(rows)
    
    sql = f"""
        INSERT INTO `tabqp_SP_DispatchSync` (
            name,
            travel_id,
            license_plate,
            bol,
            origin, 
            destination,
            bol_value,
            supplier_id, 
            creation,
            modified,
            modified_by,
            owner,
            docstatus
        ) VALUES 
        {values_query}"""
        
    frappe.db.sql(sql)


def move_to_final_dispatch():
    sql = """
        INSERT INTO `tabqp_SP_Dispatch` (
            name, 
            travel_id, 
            license_plate, 
            bol, 
            origin, 
            destination, 
            bol_value, 
            supplier,
            warehouse,
            creation, 
            modified, 
            modified_by, 
            owner, 
            docstatus
        )
        SELECT 
            sync.name,
            sync.travel_id,
            sync.license_plate,
            sync.bol,
            sync.origin,
            sync.destination,
            sync.bol_value,
            sync.supplier_id,
            warehouse.code,
            sync.creation,
            sync.modified,
            sync.modified_by,
            sync.owner,
            0
        FROM `tabqp_SP_DispatchSync` AS sync
        LEFT JOIN `tabqp_SP_DispatchWarehouse` AS warehouse ON sync.origin = warehouse.title
        LEFT JOIN `tabqp_SP_Dispatch` AS final ON sync.name = final.name
        WHERE final.bol IS NULL
    """
    
    frappe.db.sql(sql)
    