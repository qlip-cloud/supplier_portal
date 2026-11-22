def set_name(doc, method):

    # La integracion externa (BC) puede enviar la OC en `supplier_oc`, mientras
    # documenteme la lee de `qp_supplier_oc`. Mantener ambos sincronizados
    # cuando las columnas existen, sin importar cual de las dos llega.
    meta = doc.meta
    if meta.has_field("supplier_oc") and meta.has_field("qp_supplier_oc"):
        supplier_oc = doc.get("supplier_oc")
        qp_supplier_oc = doc.get("qp_supplier_oc")

        if supplier_oc and not qp_supplier_oc:
            doc.qp_supplier_oc = supplier_oc
        elif qp_supplier_oc and not supplier_oc:
            doc.supplier_oc = qp_supplier_oc

    if doc.is_new() and doc.supplier_delivery_note:
        doc.name = doc.supplier_delivery_note
        doc.flags.name_set = True
