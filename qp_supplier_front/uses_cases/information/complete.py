def handler(supplier, method):
    
    if supplier.qp_status in ("Rechazado", "En proceso"):
    
        is_completed = True
        
        for field in supplier.qp_field_validations:
            
            if field.is_completed == 0:
                
                is_completed = False
                
                break
            
        if is_completed:
            
            supplier.qp_status = "En revisión"