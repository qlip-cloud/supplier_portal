import frappe
from qp_supplier_front.uses_cases.supplier.approve import handler as approve_supplier   
from qp_supplier_front.uses_cases.tax_report.get import handler as get_report   
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def report(supplier_id, report_type, fiscal_year, bimester):
    
    try:
        
        msg = "Información aprobada correctamente."
        
        result = get_report(supplier_id, report_type, fiscal_year, bimester)
        
        frappe.local.response.filename = "report.pdf"
        frappe.local.response.filecontent = result
        frappe.local.response.type = "pdf"
        
    except Exception as error:
        
        msg = f"Error al aprobar información: {str(error)}"
        
        response(500,  msg)