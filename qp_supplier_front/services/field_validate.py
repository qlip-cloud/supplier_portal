import frappe
from qp_supplier_front.services.get_data import get_dynamic_link
import re

def handler(supplier, valid_code, count, dual_field = None, **kargs):
    if should_skip_section(supplier, valid_code):
        sections = frappe.get_list("qp_SP_FieldSection", filters={"code": valid_code}, fields=["number_valid"])
        required = int(sections[0].number_valid) if sections else 0

        add_field_validations(supplier, valid_code, count=required)
        supplier.save()
        return

    count += count_valid_fields(**kargs)
    count += get_count_dual_field(dual_field)

    add_field_validations(supplier, valid_code, count)
    set_missing_fields(supplier, valid_code, dual_field,**kargs)
    supplier.save()
    
def add_field_validations(supplier,valid_code, count):

    if not supplier.qp_field_validations:
        
        init_field_validations(supplier, valid_code, count)
        return
    
    set_field_validations(supplier, valid_code, count)
            
def set_field_validations(supplier, valid_code, count):
    
    for field_validation in supplier.qp_field_validations:

        if field_validation.field_section == valid_code:

            field_validation.number = count

            if field_validation.field_section == "international":
                if supplier.qp_financial_currency_foreigner == "NO":
                    field_validation.is_completed = count == 3
                else:
                    field_validation.is_completed = count == int(field_validation.field_number)   
            else:
                field_validation.is_completed = count == int(field_validation.field_number)
            return field_validation
            
def init_field_validations(supplier, valid_code, count):
    
    field_section = frappe.get_list("qp_SP_FieldSection", filters = {"is_active": 1}, fields = ["code", "number_valid"])
    
    for section in field_section:
        
        supplier.append("qp_field_validations", {
            "field_section": section.code,
            "number": count if valid_code == section.code else 0,
            "is_completed": count == section.number_valid if valid_code == section.code else False,
            "missing_fields": ""
        })
    
def count_valid_fields(**kargs):

    valid_count = 0
    
    if kargs:
        
        for arg in kargs.values():
        
            if is_valid(arg):
            
                valid_count += 1
    
    return valid_count

def set_missing_fields(supplier, valid_code, dual_field=None, **kargs):
    for field_validation in supplier.qp_field_validations:

        if field_validation.field_section == valid_code:

            if field_validation.is_completed:
                field_validation.missing_fields = ""
            else:
                missing_fields = []
                if kargs:
                    for key, value in kargs.items():
                        if not is_valid(value):
                            missing_fields.append(key)

                if dual_field:
                    for field in dual_field:
                        condition_field = field["condition_value"]
                        dependent_field = field.get("dependent_value")

                        if is_valid(condition_field):
                            if condition_field == "SI" and not is_valid(dependent_field):
                                missing_fields.append(f"{field.get('dependent_name')}")
                            elif condition_field == "NO":
                                continue
                        else:
                            missing_fields.append(f"{field.get('condition_name')}")
                field_validation.missing_fields = ",".join(missing_fields)
            return field_validation.missing_fields
        
def is_valid(value):
        
        return value is not None and (str(value).strip() != "" and value != "0")
    
def validate_field_list(supplier,doctype, valid_code, fields_to_validate):

    doctypes = get_dynamic_link(supplier, doctype)
    
    setup_validate_field_list(supplier, doctypes, valid_code, fields_to_validate)
    
def validate_field_list_with_table(supplier,doctype, valid_code, fields_to_validate, tables = None):

    if valid_code == "contact":
        validate_complete_contacts_by_type(supplier, doctype, valid_code)
        return
    
    doctypes = get_dynamic_link(supplier, doctype)
    
    count = get_count(doctypes, fields_to_validate)
    
    count += get_count_by_table(doctypes, tables)                
            
    add_field_validations(supplier,valid_code, count)

def get_count_dual_field(dual_field=None):
    count = 0

    if dual_field:
        for field in dual_field:
            condition_field = field["condition_value"]
            dependent_field = field.get("dependent_value")

            if is_valid(condition_field):
                if condition_field == "SI" and is_valid(dependent_field):
                    count += 1
                elif condition_field == "NO":
                    count += 1

    return count


def get_count_by_table(doctypes, tables = None):
    if tables:
        count_by_table = None

        for doctype in doctypes:
            count_line = 0

            for key, table in tables.items():
                data = getattr(doctype, key, None)
                if data is None:
                    continue 
                count = get_count(data, table)
                count_line += count if count is not None else 0

            if count_by_table is None or count_line < count_by_table:
                count_by_table = count_line

        if count_by_table is None:
            frappe.throw("Error en el diccionario de validaciones")  

        return count_by_table

    return 0

    
def setup_validate_field_list(supplier, doctypes, valid_code, fields_to_validate):
    
    count = get_count(doctypes, fields_to_validate)
            
    add_field_validations(supplier,valid_code, count)
    
def get_count(doctypes, fields_to_validate):
    
    count = None
    
    for doctype in doctypes:
        
        count_line = count_valid_fields(*[getattr(doctype, field) for field in fields_to_validate])
                
        if count is None or count_line < count:
            
            count = count_line
            
    return count if count is not None else 0

def should_skip_section(supplier, section_code):

    if section_code == "international" and supplier.qp_is_foreigner_supplier:

        return True
    
    return False

def validate_complete_contacts_by_type(supplier, doctype, valid_code):
    required_types = {"Comercial", "Compras", "Finanzas", "Cartera"}
    contacts = get_dynamic_link(supplier, doctype)

    valid_types = set()

    for contact in contacts:
        contact_type = getattr(contact, "qp_contact_type", None)
        if contact_type in required_types:
            has_name = is_valid(getattr(contact, "first_name", None))
            has_email = contact.email_ids and is_valid(contact.email_ids[0].email_id)
            has_phone = contact.phone_nos and is_valid(contact.phone_nos[0].phone)

            if has_name and has_email and has_phone:
                valid_types.add(contact_type)

    count = len(valid_types) 
    add_field_validations(supplier, valid_code, count)


def validar_supplier_name(supplier_name):
    if len(supplier_name) > 65:
        frappe.throw("El nombre excede los 65 caracteres.")
    
    # Solo permite letras, números, espacios y punto
    if not re.match(r'^[a-zA-Z0-9. ]*$', supplier_name):
        frappe.throw("El nombre contiene caracteres no permitidos.")