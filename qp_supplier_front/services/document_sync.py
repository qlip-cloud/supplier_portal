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
    log.supplier = supplier_id
    log.tax_id = tax_id
    log.endpoint_code = endpoint_code
    log.payload = payload
    log.response = json.dumps(response) if not isinstance(response, str) else response
    log.status = "Success" if status == 200 else "Error"

    if status != 200:
        log.error_message = get_response_description(response) or json.dumps(response)

    log.insert()
    return log


def convert_to_mariadb_datetime(value):
    if value and isinstance(value, str) and len(value) >= 19:
        converted = value[:19].replace("T", " ")
        if converted.startswith("0001"):
            return None
        return converted
    return value


def create_sync_line(log_name, doc_data):
    import frappe
    line = frappe.new_doc("qp_SP_DocumentSyncLine")
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
    line.insert()
    return line


def create_sync_lines(log_name, ldocuments):
    for doc_data in ldocuments:
        create_sync_line(log_name, doc_data)
