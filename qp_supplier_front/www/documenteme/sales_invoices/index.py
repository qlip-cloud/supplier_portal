import frappe
from qp_supplier_front.services.get_data import has_recent_news, get_has_dispatch_permission

def get_context(context):
    context.no_cache = True

    query_params = frappe.request.args
    supplier_id = query_params.get("supplier")
    context.supplier_id = supplier_id
    context.has_dispatch_permission = get_has_dispatch_permission(supplier_id)
    context.has_recent_news = has_recent_news()
    context.show_result = True

    context.facturas = [
        {
            "name": "INV-001",
            "nit": "900123456-7",
            "factura_proveedor": "F-2024-001",
            "factura_interna": "INT-001",
            "fecha": "2025-06-15",
            "orden_compra": "OC-2024-100",
            "recepcion": "REC-2024-050",
            "subtotal": 5000000,
            "iva": 950000,
            "total": 5950000,
            "estado": "Registrado",
            "fecha_vencimiento": "2025-07-15",
            "productos_factura": [
                {"codigo": "PROD-001", "udm": "UN", "cantidad": 10, "valor_unitario": 250000, "valor_total": 2500000},
                {"codigo": "PROD-002", "udm": "UN", "cantidad": 5, "valor_unitario": 500000, "valor_total": 2500000},
            ],
            "productos_orden_compra": [
                {"codigo": "PROD-001", "udm": "UN", "cantidad": 10, "valor_unitario": 250000, "valor_total": 2500000},
            ],
            "productos_recepcion": [
                {"codigo": "PROD-001", "udm": "UN", "cantidad": 10, "valor_unitario": 250000, "valor_total": 2500000},
            ]
        },
        {
            "name": "INV-002",
            "nit": "890987654-3",
            "factura_proveedor": "F-2024-002",
            "factura_interna": "",
            "fecha": "2025-06-10",
            "orden_compra": "",
            "recepcion": "",
            "subtotal": 3200000,
            "iva": 608000,
            "total": 3808000,
            "estado": "Por Recibir",
            "fecha_vencimiento": "2025-07-10",
            "productos_factura": [
                {"codigo": "PROD-003", "udm": "KG", "cantidad": 100, "valor_unitario": 32000, "valor_total": 3200000},
            ],
            "productos_orden_compra": [],
            "productos_recepcion": [],
        },
        {
            "name": "INV-003",
            "nit": "900123456-7",
            "factura_proveedor": "F-2024-003",
            "factura_interna": "INT-002",
            "fecha": "2025-06-05",
            "orden_compra": "OC-2024-101",
            "recepcion": "",
            "subtotal": 15000000,
            "iva": 2850000,
            "total": 17850000,
            "estado": "Rechazada",
            "fecha_vencimiento": "2025-07-05",
            "productos_factura": [
                {"codigo": "PROD-004", "udm": "LTR", "cantidad": 50, "valor_unitario": 300000, "valor_total": 15000000},
            ],
            "productos_orden_compra": [
                {"codigo": "PROD-004", "udm": "LTR", "cantidad": 50, "valor_unitario": 300000, "valor_total": 15000000},
            ],
            "productos_recepcion": [],
        },
        {
            "name": "INV-004",
            "nit": "765432109-8",
            "factura_proveedor": "F-2024-004",
            "factura_interna": "INT-003",
            "fecha": "2025-06-01",
            "orden_compra": "OC-2024-102",
            "recepcion": "REC-2024-051",
            "subtotal": 8750000,
            "iva": 1662500,
            "total": 10412500,
            "estado": "Lista para Registro",
            "fecha_vencimiento": "2025-07-01",
            "productos_factura": [
                {"codigo": "PROD-005", "udm": "MTS", "cantidad": 200, "valor_unitario": 25000, "valor_total": 5000000},
                {"codigo": "PROD-006", "udm": "UN", "cantidad": 15, "valor_unitario": 250000, "valor_total": 3750000},
            ],
            "productos_orden_compra": [
                {"codigo": "PROD-005", "udm": "MTS", "cantidad": 200, "valor_unitario": 25000, "valor_total": 5000000},
                {"codigo": "PROD-006", "udm": "UN", "cantidad": 15, "valor_unitario": 250000, "valor_total": 3750000},
            ],
            "productos_recepcion": [
                {"codigo": "PROD-005", "udm": "MTS", "cantidad": 200, "valor_unitario": 25000, "valor_total": 5000000},
            ]
        }
    ]
