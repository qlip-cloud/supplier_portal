import frappe

def create_doc(docs, fiels, table):
    
    docs_values = list(docs.values())
    
    values = converter_list_to_sql_values(docs_values)
    
    insert_sql(fiels, values, table)
    
def converter_list_to_sql_values(values):
    
    return str(values).replace("[","").replace("]","")

def insert_sql(field, values, table):
    
    sql = f"""
        INSERT INTO {table} {field}
        VALUES
        {values}
        """
    frappe.db.sql(sql)