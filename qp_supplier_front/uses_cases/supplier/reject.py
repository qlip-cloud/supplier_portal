from qp_supplier_front.services.get_data import get_supplier
REJECT = "Rechazado"

def handler(supplier_id, qp_reject_observation):
    
    supplier = get_supplier(supplier_id)
    
    supplier.qp_status = REJECT
    
    supplier.qp_preapproved = False
    
    supplier.qp_reject_observation = qp_reject_observation
    
    supplier.save()

    return {
        "supplier": supplier
    }