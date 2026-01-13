
import frappe
from qp_supplier_front.services.get_data import get_supplier
from qp_supplier_front.services.field_validate import setup_validate_field_list

def handler(supplier_id, shareholder_id):

  frappe.db.delete("qp_SP_ShareHolder", {"name": shareholder_id, "parent": supplier_id})
  frappe.db.commit()
  
  supplier = get_supplier(supplier_id)
  supplier.save()
  fields_to_validate = ["fullname", "nationality", "have_resident_another_country", "have_american_visa", "id_type", "tax_id", "market_share"]

  setup_validate_field_list(supplier, supplier.qp_shareholders, "shareholder", fields_to_validate)
  
  list = frappe.render_template("qp_supplier_front/templates/list/information/shareholders.html", {
      "supplier": supplier
  })
  
  result = {
      "supplier": supplier.as_dict(),
      "render": {"list": list, "is_estatus_editable": True, "container": "shareholder_list"},
  }

  return result