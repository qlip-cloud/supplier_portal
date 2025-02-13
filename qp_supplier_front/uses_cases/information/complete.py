def handler(supplier):
        
    is_completed = True
    
    for field in supplier.qp_field_validations:
        
        if field.is_completed == 0:
            
            is_completed = False
            
            break
        
    if supplier.qp_field_validations and is_completed:
        
        supplier.qp_status = "En revisión"
        
        supplier.save()