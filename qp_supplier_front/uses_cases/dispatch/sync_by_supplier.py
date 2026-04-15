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

    result = get_result(endpoint, supplier_id)

    sync_dispatch_fast(result, supplier_id)
    
    mark_dispatch_error(supplier_id)

    move_to_dispatch(supplier_id)
    
    move_to_dispatch_line(supplier_id)
    
    frappe.db.commit()
    
def sync_dispatch_fast(json_data, supplier_id):
    
    bols = json_data.get("Bols", [])
    
    if not bols:
    
        return 0
    
    frappe.db.sql(f"DELETE FROM `tabqp_SP_DispatchSync` where supplier_id = '{supplier_id}'")

    now = frappe.utils.now()
    
    rows = []
    
    for bol in bols:
        
        row = str((
            bol.get("Bol").strip() if bol.get("Bol") else "",
            bol.get("TravelId").strip() if bol.get("TravelId") else "",
            bol.get("LicensePlate").strip() if bol.get("LicensePlate") else "",
            bol.get("Bol").strip() if bol.get("Bol") else "",
            bol.get("Origin").strip() if bol.get("Origin") else "",
            bol.get("Destination").strip() if bol.get("Destination") else "",
            bol.get("BolValue") or 0,
            bol.get("TravelDate"),
            supplier_id,
            now,
            now,
            'Administrator',
            'Administrator',
            0
        ))
        rows.append(row)
    
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
            travel_date,
            supplier_id, 
            creation,
            modified,
            modified_by,
            owner,
            docstatus
        ) VALUES 
        {values_query}"""
        
    frappe.db.sql(sql)

    frappe.db.commit()

def mark_dispatch_error(supplier_id):
    
    sql = f"""UPDATE `tabqp_SP_DispatchSync` AS target
        INNER JOIN (
            SELECT travel_id, travel_date
            FROM `tabqp_SP_DispatchSync`
            WHERE travel_id IS NOT NULL 
            AND supplier_id = '{supplier_id}'
            GROUP BY travel_id, travel_date
            HAVING COUNT(DISTINCT 
                CONCAT_WS('|', 
                    IFNULL(license_plate, ''), 
                    IFNULL(origin, ''), 
                    IFNULL(travel_date, ''), 
                    IFNULL(destination, ''), 
                    IFNULL(bol_value, 0),
                    IFNULL(travel_date, '')
                )
            ) > 1
        ) AS errors ON target.travel_id = errors.travel_id and target.travel_date = errors.travel_date
        SET target.is_error = 1
        WHERE target.supplier_id = '{supplier_id}'"""

    frappe.db.sql(sql)

    frappe.db.commit()

def move_to_dispatch(supplier_id):
    
    sql = f"""
        INSERT INTO `tabqp_SP_Dispatch` (
            name, 
            travel_id, 
            license_plate, 
            origin, 
            destination, 
            travel_amount,
            travel_date,
            supplier,
            warehouse,
            creation, 
            modified, 
            modified_by, 
            owner, 
            docstatus
        )
        SELECT 
            CASE 
                WHEN sync.travel_id IS NULL OR sync.travel_id = '' THEN UUID()
                ELSE CONCAT(sync.travel_id,":", sync.travel_date)
            END AS name,
            sync.travel_id,
            sync.license_plate,
            sync.origin,
            sync.destination,
            sync.bol_value,
            sync.travel_date,
            sync.supplier_id,
            warehouse.code,
            sync.creation,
            sync.modified,
            sync.modified_by,
            sync.owner,
            0
        FROM `tabqp_SP_DispatchSync` AS sync
        LEFT JOIN `tabqp_SP_DispatchWarehouse` AS warehouse ON sync.origin = warehouse.title
        LEFT JOIN `tabqp_SP_Dispatch` AS final ON sync.travel_id = final.travel_id
        WHERE final.travel_id IS NULL and sync.travel_id is not null and sync.supplier_id = '{supplier_id}' AND sync.is_error = 0
        group by 
            sync.travel_id,
            sync.license_plate,
            sync.origin,
            sync.destination,
            sync.bol_value,
            sync.supplier_id,
            sync.travel_date,
            warehouse.code,
            sync.creation,
            sync.modified,
            sync.modified_by,
            sync.owner
    """
    print(sql)
    frappe.db.sql(sql)
    
def move_to_dispatch_line(supplier_id):
    sql = f"""
        INSERT INTO `tabqp_SP_DispatchLine` (
            name, 
            bol, 
            parent,
            parentfield,
            parenttype,
            creation, 
            modified, 
            modified_by, 
            owner
        )
        SELECT 
            sync.name,
            sync.bol,
            dispatch.name,
            'bols' as parentfield,
            'qp_SP_Dispatch' as parenttype,
            sync.creation,
            sync.modified,
            sync.modified_by,
            sync.owner
        FROM `tabqp_SP_DispatchSync` AS sync
        INNER JOIN (
            SELECT
                name, 
                travel_id, 
                license_plate, 
                origin, 
                destination, 
                travel_amount,
                travel_date,
                supplier,
                warehouse,
                creation, 
                modified, 
                modified_by, 
                owner
            FROM tabqp_SP_Dispatch AS dispatch
            where supplier = '{supplier_id}'
        ) as dispatch
        on (
                dispatch.travel_id = sync.travel_id
            AND dispatch.license_plate = sync.license_plate
            AND dispatch.origin = sync.origin
            AND dispatch.destination = sync.destination
            AND dispatch.travel_amount = sync.bol_value
            AND dispatch.supplier = sync.supplier_id
            AND dispatch.travel_date = sync.travel_date
            AND dispatch.creation = sync.creation
            AND dispatch.modified = sync.modified
            AND dispatch.modified_by = sync.modified_by
            AND dispatch.owner = sync.owner
            AND sync.is_error = 0
        )
        LEFT JOIN `tabqp_SP_DispatchLine` AS final ON sync.name = final.name
        WHERE final.bol IS NULL
        
    """
    
    frappe.db.sql(sql)
    