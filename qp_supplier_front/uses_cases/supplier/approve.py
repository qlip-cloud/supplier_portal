from qp_supplier_front.services.get_data import get_supplier
APPROVE = "Aprobado"

def handler(supplier_id):
    
    supplier = get_supplier(supplier_id)
    
    supplier.qp_status = APPROVE
    
    supplier.save()


    return {
        "supplier": supplier
    }