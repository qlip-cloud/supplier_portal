def build_document_params(tax_id, nvfac_esta, nvfac_fini, nvfac_ffin):
    return (
        "nvemp_nnit={tax_id}"
        "&nvfac_esta={nvfac_esta}"
        "&nvfac_fini={nvfac_fini}"
        "&nvfac_ffin={nvfac_ffin}"
    ).format(tax_id=tax_id, nvfac_esta=nvfac_esta,
             nvfac_fini=nvfac_fini, nvfac_ffin=nvfac_ffin)


def is_successful_response(response, status):
    return status == 200 and isinstance(response, dict) and response.get("Result") == 0


def get_response_description(response):
    return response.get("Description") if isinstance(response, dict) else None


def create_sync_log(supplier_id, tax_id, endpoint_code, payload, response, status):
    import frappe
    import json
    log = frappe.new_doc("qp_SP_DocumentSyncLog")
    if supplier_id and frappe.db.exists("Supplier", supplier_id):
        log.supplier = supplier_id
    log.tax_id = tax_id
    log.endpoint_code = endpoint_code
    log.payload = payload
    log.response = json.dumps(response) if not isinstance(response, str) else response
    log.status = "Success" if status == 200 else "Error"

    if status != 200:
        log.error_message = get_response_description(response) or json.dumps(response)

    log.insert(ignore_permissions=True)
    return log.name


def convert_to_mariadb_datetime(value):
    if value and isinstance(value, str) and len(value) >= 19:
        converted = value[:19].replace("T", " ")
        if converted.startswith("0001"):
            return None
        return converted
    return value


def _set_sync_line_fields(line, log_name, doc_data):
    line.document_sync_log = log_name
    line.nvfac_cont = doc_data.get("Nvfac_cont")
    line.nvtip_docu = doc_data.get("Nvtip_docu")
    line.nvfac_nume = doc_data.get("Nvfac_nume")
    line.nvfac_cufe = doc_data.get("Nvfac_cufe")
    line.nvpro_nomb = doc_data.get("Nvpro_nomb")
    line.nvpro_ndoc = doc_data.get("Nvpro_ndoc")
    line.nvfac_fech = convert_to_mariadb_datetime(doc_data.get("Nvfac_fech"))
    line.nvmon_codi = doc_data.get("Nvmon_codi")
    line.nvfac_totp = doc_data.get("Nvfac_totp")
    line.nvfac_esta = doc_data.get("Nvfac_esta")
    line.nvfac_rfec = convert_to_mariadb_datetime(doc_data.get("Nvfac_rfec"))
    line.nvfac_orde = doc_data.get("Nvfac_orde")
    line.nvfac_rece = doc_data.get("Nvfac_rece")
    line.nvfac_refe = doc_data.get("Nvfac_refe")
    line.nvsuc_codi = doc_data.get("Nvsuc_codi")
    line.nvfac_venc = convert_to_mariadb_datetime(doc_data.get("Nvfac_venc"))
    line.nvfac_viva = doc_data.get("Nvfac_viva")
    line.nvpro_ufac = convert_to_mariadb_datetime(doc_data.get("Nvpro_ufac"))
    line.nvfac_vinc = doc_data.get("Nvfac_vinc")
    line.nvfac_vicb = doc_data.get("Nvfac_vicb")
    line.nvfac_ueve = doc_data.get("Nvfac_ueve")
    line.nvfac_stot = doc_data.get("Nvfac_stot")
    line.nvfac_vicl = doc_data.get("Nvfac_vicl")
    line.nvfac_vinp = doc_data.get("Nvfac_vinp")
    line.nvfac_vibu = doc_data.get("Nvfac_vibu")
    line.nvfac_vicu = doc_data.get("Nvfac_vicu")
    line.nvfac_vadv = doc_data.get("Nvfac_vadv")
    return line


def create_sync_line(log_name, doc_data):
    import frappe

    nvfac_nume = doc_data.get("Nvfac_nume")
    nvpro_ndoc = doc_data.get("Nvpro_ndoc")

    sync_line_name = build_sync_line_name(nvpro_ndoc, nvfac_nume)

    if frappe.db.exists("qp_SP_DocumentSyncLine", sync_line_name):
        line = frappe.get_doc("qp_SP_DocumentSyncLine", sync_line_name)
        line = _set_sync_line_fields(line, log_name, doc_data)
        line.save(ignore_permissions=True)
        return line

    existing = _get_existing_sync_line(nvpro_ndoc, nvfac_nume)
    if existing:
        line = frappe.get_doc("qp_SP_DocumentSyncLine", existing)
        line = _set_sync_line_fields(line, log_name, doc_data)
        line.save(ignore_permissions=True)
        return line

    line = frappe.new_doc("qp_SP_DocumentSyncLine")
    line = _set_sync_line_fields(line, log_name, doc_data)
    line.insert(ignore_permissions=True)
    return line


def build_sync_line_name(nvpro_ndoc, nvfac_nume):
    """Nombre (autoname) de qp_SP_DocumentSyncLine: {nvpro_ndoc}:{nvfac_nume}."""
    if not nvpro_ndoc:
        return nvfac_nume
    return "{}:{}".format(nvpro_ndoc, nvfac_nume)


def _get_existing_sync_line(nvpro_ndoc, nvfac_nume):
    """Busca una SyncLine previa del mismo proveedor y numero de factura.

    Cubre el formato legacy (name == nvfac_nume) y el prefijado, para
    reutilizar la linea ya sincronizada (sin duplicarla ni forzar una
    re-sincronizacion del detalle). Retorna el name o None.
    """
    import frappe

    if not nvfac_nume:
        return None
    filters = {"nvfac_nume": nvfac_nume}
    if nvpro_ndoc:
        filters["nvpro_ndoc"] = nvpro_ndoc
    names = frappe.get_all(
        "qp_SP_DocumentSyncLine",
        filters=filters,
        pluck="name",
        limit=1,
    )
    return names[0] if names else None


def create_sync_lines(log_name, ldocuments):
    for doc_data in ldocuments:
        if not doc_data.get("Nvfac_ueve"):
            create_sync_line(log_name, doc_data)


def build_detail_params(nvemp_nnit, nvpro_ndoc, nvfac_esta, nvfac_nume):
    return (
        "nvemp_nnit={nvemp_nnit}"
        "&nvfac_esta={nvfac_esta}"
        "&nvfac_nume={nvfac_nume}"
        "&nvpro_docu={nvpro_docu}"
    ).format(nvemp_nnit=nvemp_nnit, nvfac_esta=nvfac_esta,
             nvfac_nume=nvfac_nume, nvpro_docu=nvpro_ndoc)


def get_log_company_tax_id(log_name):
    import frappe
    if not log_name:
        return None
    return frappe.db.get_value("qp_SP_DocumentSyncLog", log_name, "tax_id")


def get_uncompleted_lines():
    import frappe
    return frappe.get_all(
        "qp_SP_DocumentSyncLine",
        filters={"is_completed": 0},
        fields=["name", "document_sync_log", "nvpro_ndoc", "nvfac_esta", "nvfac_nume"]
    )


def create_attached_file(detail_name, attached_item):
    import frappe
    import base64
    file_name = attached_item.get("Nvdoc_nomb")
    file_type = attached_item.get("Nvdoc_tipo")
    file_content_b64 = attached_item.get("Nvdoc_file")

    if not file_content_b64:
        return None

    content = base64.b64decode(file_content_b64)

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "content": content,
        "attached_to_doctype": "qp_SP_DocumentDetail",
        "attached_to_name": detail_name,
    })
    file_doc.save(ignore_permissions=True)

    return file_doc


def create_detail_line(detalle_item):
    import frappe
    line = frappe.new_doc("qp_SP_DetailLine")
    line.nvdet_cont = detalle_item.get("Nvdet_cont")
    line.nvpro_codi = detalle_item.get("Nvpro_codi")
    line.nvdet_desc = detalle_item.get("Nvdet_desc")
    line.nvdet_tcan = detalle_item.get("Nvdet_tcan")
    line.nvdet_valo = detalle_item.get("Nvdet_valo")
    line.nvdet_stot = detalle_item.get("Nvdet_stot")
    line.nvdet_orde = detalle_item.get("Nvdet_orde")
    line.nvdet_rece = detalle_item.get("Nvdet_rece")
    line.nvdet_vdes = detalle_item.get("Nvdet_vdes")
    line.nvuni_desc = detalle_item.get("Nvuni_desc")
    line.nvdet_nota = detalle_item.get("Nvdet_nota")

    for impuesto in (detalle_item.get("lImpuestos") or []):
        tax_line = line.append("impuestos")
        tax_line.nvimp_cdia = impuesto.get("Nvimp_cdia")
        tax_line.nvimp_desc = impuesto.get("Nvimp_desc")
        tax_line.nvimp_base = impuesto.get("Nvimp_base")
        tax_line.nvimp_valo = impuesto.get("Nvimp_valo")
        tax_line.nvimp_porc = impuesto.get("Nvimp_porc")

    return line


ADVANCED_STATES = ("BCC", "PA", "A", "R")


def _resolve_sync_state(current_state, origin_state, origin_ueve):
    """Resuelve el nvfac_esta tras una re-sincronizacion.

    El estado local que ya avanzo el flujo (creado en BC, en proceso,
    aprobado o rechazado) NO debe retroceder al estado de analisis (V/E/T)
    que documenteme aun reporta. Por el contrario, un estado definitivo de
    origen (A/R) o un evento (nvfac_ueve) de documenteme prevalece porque
    refleja una confirmacion real del origen.

    - current_state: estado local previo (o None si es detalle nuevo).
    - origin_state:  Nvfac_esta que devuelve documenteme.
    - origin_ueve:   Nvfac_ueve que devuelve documenteme.
    """
    if origin_state in ("A", "R") or origin_ueve:
        return origin_state
    if current_state in ADVANCED_STATES:
        return current_state
    return origin_state


def _set_document_detail_fields(doc, document_data):
    current_state = doc.get("nvfac_esta")
    origin_state = document_data.get("Nvfac_esta")
    origin_ueve = document_data.get("Nvfac_ueve")
    doc.nvfac_cont = document_data.get("Nvfac_cont")
    doc.nvtip_docu = document_data.get("Nvtip_docu")
    doc.nvfac_nume = document_data.get("Nvfac_nume")
    doc.nvfac_cufe = document_data.get("Nvfac_cufe")
    doc.nvpro_nomb = document_data.get("Nvpro_nomb")
    doc.nvpro_ndoc = document_data.get("Nvpro_ndoc")
    doc.nvfac_fech = convert_to_mariadb_datetime(document_data.get("Nvfac_fech"))
    doc.nvmon_codi = document_data.get("Nvmon_codi")
    doc.nvfac_totp = document_data.get("Nvfac_totp")
    doc.nvfac_esta = _resolve_sync_state(current_state, origin_state, origin_ueve)
    doc.nvfac_rfec = convert_to_mariadb_datetime(document_data.get("Nvfac_rfec"))
    doc.nvfac_orde = document_data.get("Nvfac_orde")
    doc.nvfac_rece = document_data.get("Nvfac_rece")
    doc.nvfac_refe = document_data.get("Nvfac_refe")
    doc.nvsuc_codi = document_data.get("Nvsuc_codi")
    doc.nvfac_venc = convert_to_mariadb_datetime(document_data.get("Nvfac_venc"))
    doc.nvfac_viva = document_data.get("Nvfac_viva")
    doc.nvpro_ufac = convert_to_mariadb_datetime(document_data.get("Nvpro_ufac"))
    doc.nvfac_ueve = document_data.get("Nvfac_ueve")
    doc.nvfac_stot = document_data.get("Nvfac_stot")
    doc.nvfac_vinc = document_data.get("Nvfac_vinc")
    doc.nvfac_vicb = document_data.get("Nvfac_vicb")
    doc.nvfac_vicl = document_data.get("Nvfac_vicl")
    doc.nvfac_vinp = document_data.get("Nvfac_vinp")
    doc.nvfac_vibu = document_data.get("Nvfac_vibu")
    doc.nvfac_vicu = document_data.get("Nvfac_vicu")
    doc.nvfac_vadv = document_data.get("Nvfac_vadv")
    doc.nvfac_conv = document_data.get("Nvfac_conv")
    doc.nvfac_fpag = document_data.get("Nvfac_fpag")
    doc.nvpro_cciu = document_data.get("Nvpro_cciu")
    doc.nvpro_ciud = document_data.get("Nvpro_ciud")
    doc.nvpro_cpai = document_data.get("Nvpro_cpai")
    doc.nvpro_pais = document_data.get("Nvpro_pais")
    doc.nvpro_dire = document_data.get("Nvpro_dire")
    doc.nvfac_tota = document_data.get("Nvfac_tota")
    doc.nvfac_votr = document_data.get("Nvfac_votr")
    return doc


def _create_allowance_charges_from_xml(detail, attached_list):
    import base64
    from qp_supplier_front.services.xml_allowance_charge import extract_document_allowance_charges

    for attached_item in (attached_list or []):
        if attached_item.get("Nvdoc_tipo") != "XML":
            continue
        file_content_b64 = attached_item.get("Nvdoc_file")
        if not file_content_b64:
            continue
        xml_content = base64.b64decode(file_content_b64)
        for charge in extract_document_allowance_charges(xml_content):
            row = detail.append("allowance_charges", {})
            row.charge_indicator = charge.get("charge_indicator", 0)
            row.reason_code = charge.get("reason_code")
            row.reason = charge.get("reason")
            row.multiplier_factor = charge.get("multiplier_factor")
            row.amount = charge.get("amount")
            row.currency = charge.get("currency")
            row.base_amount = charge.get("base_amount")

def _get_existing_detail_name(nvfac_nume, nvpro_ndoc=None):
    import frappe
    if not nvfac_nume:
        return None
    filters = {"nvfac_nume": nvfac_nume}
    if nvpro_ndoc:
        filters["nvpro_ndoc"] = nvpro_ndoc
    names = frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
        pluck="name",
        limit=1,
    )
    return names[0] if names else None


def create_document_detail(document_sync_line_name, document_data, attached_list):
    import frappe

    nvfac_nume = document_data.get("Nvfac_nume")
    nvpro_ndoc = document_data.get("Nvpro_ndoc")
    detail_name = _get_existing_detail_name(nvfac_nume, nvpro_ndoc)

    if detail_name:
        detail = frappe.get_doc("qp_SP_DocumentDetail", detail_name)
        detail = _set_document_detail_fields(detail, document_data)
        detail.document_sync_line = document_sync_line_name

        # Clean up old File docs before clearing child table
        old_file_ids = frappe.db.sql_list(
            "SELECT file_id FROM `tabqp_SP_DocumentAttach` WHERE parent=%s",
            detail_name
        )
        for file_id in old_file_ids:
            if file_id:
                frappe.delete_doc("File", file_id, ignore_permissions=True, force=True)

        # Remove old child rows from DB
        frappe.db.sql("DELETE FROM `tabqp_SP_DetailLine` WHERE parent=%s", detail_name)
        frappe.db.sql("DELETE FROM `tabqp_SP_DocumentAttach` WHERE parent=%s", detail_name)
        frappe.db.sql("DELETE FROM `tabqp_SP_AllowanceCharge` WHERE parent=%s", detail_name)

        # Clear the child rows already loaded in memory by get_doc, otherwise
        # save() re-persists the stale rows and _validate_links fails on the
        # File links that were deleted above.
        detail.detail_lines = []
        detail.attached_files = []
        detail.allowance_charges = []

        # Re-populate detail lines
        for detalle_item in (document_data.get("Detalle") or []):
            detail.append("detail_lines", create_detail_line(detalle_item))

        # Re-populate attached files
        for attached_item in (attached_list or []):
            file_doc = create_attached_file(detail_name, attached_item)
            if file_doc:
                attach_row = detail.append("attached_files")
                attach_row.file_name = attached_item.get("Nvdoc_nomb")
                attach_row.file_type = attached_item.get("Nvdoc_tipo")
                attach_row.file_url = file_doc.file_url
                attach_row.file_id = file_doc.name

        _create_allowance_charges_from_xml(detail, attached_list)

        detail.save(ignore_permissions=True)
        return detail

    detail = frappe.new_doc("qp_SP_DocumentDetail")
    detail.document_sync_line = document_sync_line_name
    detail = _set_document_detail_fields(detail, document_data)

    for detalle_item in (document_data.get("Detalle") or []):
        detail_line = create_detail_line(detalle_item)
        detail.append("detail_lines", detail_line)

    detail.insert(ignore_permissions=True)

    for attached_item in (attached_list or []):
        file_doc = create_attached_file(detail.name, attached_item)
        if file_doc:
            attach_row = detail.append("attached_files")
            attach_row.file_name = attached_item.get("Nvdoc_nomb")
            attach_row.file_type = attached_item.get("Nvdoc_tipo")
            attach_row.file_url = file_doc.file_url
            attach_row.file_id = file_doc.name

    _create_allowance_charges_from_xml(detail, attached_list)

    detail.save(ignore_permissions=True)

    return detail


def log_sync_attempt(line_name, status, error_message, response):
    import frappe
    import json
    from datetime import datetime

    line = frappe.get_doc("qp_SP_DocumentSyncLine", line_name)
    attempt = line.append("sync_attempts")
    attempt.attempt_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    attempt.status = status
    attempt.error_message = error_message
    attempt.response = json.dumps(response) if not isinstance(response, str) else response
    line.save(ignore_permissions=True)


def mark_line_completed(line_name):
    import frappe
    line = frappe.get_doc("qp_SP_DocumentSyncLine", line_name)
    line.is_completed = 1
    line.save(ignore_permissions=True)
