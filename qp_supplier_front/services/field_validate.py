import frappe
from qp_supplier_front.services.get_data import get_dynamic_link

def handler(supplier, valid_code, count, dual_field = None, *args):
    
    count += count_valid_fields(*args)
    
    count += get_count_dual_field(dual_field)
    
    add_field_validations(supplier,valid_code, count)
    
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
            
            field_validation.is_completed = count == int(field_validation.field_number)
            
            return field_validation
            
def init_field_validations(supplier, valid_code, count):
    
    field_section = frappe.get_list("qp_SP_FieldSection", filters = {"is_active": 1}, fields = ["code", "number_valid"])
    
    for section in field_section:
        
        supplier.append("qp_field_validations", {
            "field_section": section.code,
            "number": count if valid_code == section.code else 0,
            "is_completed": count == section.number_valid if valid_code == section.code else False
        })
    
def count_valid_fields(*args):

    valid_count = 0
    
    if args:
        
        for arg in args:
        
            if is_valid(arg):
            
                valid_count += 1
    
    return valid_count

def is_valid(value):
        
        return value is not None and (str(value).strip() != "" and value != "0")
    
def validate_field_list(supplier,doctype, valid_code, fields_to_validate):

    doctypes = get_dynamic_link(supplier, doctype)
    
    setup_validate_field_list(supplier, doctypes, valid_code, fields_to_validate)
    
def validate_field_list_with_table(supplier,doctype, valid_code, fields_to_validate, tables = None):
    
    doctypes = get_dynamic_link(supplier, doctype)
    
    count = get_count(doctypes, fields_to_validate)
    
    count += get_count_by_table(doctypes, tables)                
            
    add_field_validations(supplier,valid_code, count)

def get_count_dual_field(dual_field = None):
    
    count = 0

    if dual_field:
        
        for field in dual_field:
            
            if field[0] == "SI" and is_valid(field[0]):
                
                count += 1    
    
    return count

def get_count_by_table(doctypes, tables = None):
    
    if tables:
    
        count_by_table = None
        
        for doctype in doctypes:
            
            count_line = 0
            
            for key, table in tables.items():
            
                count_line += get_count(getattr(doctype, key), table)
                
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
            
    return count