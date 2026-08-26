import frappe
from qp_supplier_front.uses_cases.documents.sync_by_supplier import (
    sync_by_supplier,
    get_default_nvfac_fini,
    get_default_nvfac_ffin,
)
from qp_supplier_front.uses_cases.documents.sync_detail import sync_detail
from qp_supplier_front.services.document_sync import (
    create_sync_log,
    create_sync_lines,
    get_uncompleted_lines,
    get_log_company_tax_id,
    create_document_detail,
    log_sync_attempt,
    mark_line_completed,
)
from qp_supplier_front.services import sync_lock
from qp_authorization.use_case.basic.authorize import send_request_status
from qp_supplier_front.resources.documenteme.auto_assign import run_auto_assign
from qp_supplier_front.resources.documenteme.auto_approve import run_auto_approve
from qp_supplier_front.resources.documenteme.auto_reject import run_auto_reject
from qp_supplier_front.resources.documenteme.stale_status_alert import generate_stale_status_alerts

DOCUMENTS_LOCK_DOMAIN = "documents"


def get_company_tax_id(company_name):
    return frappe.get_doc("Company", company_name).tax_id


def _sync_documents(nvfac_esta=None, nvfac_fini=None, nvfac_ffin=None,
                    doc_names=None):
    """Fase SINCRONA del flujo documenteme (no depende de workers).

    Genera primero las alertas de estatus no definitivo (>48h): solo leen
    qp_SP_DocumentDetail e insertan en la child table qp_SP_Alert, asi que
    se ejecutan aunque el sync posterior falle (red, permisos o workers).
    Luego descarga lineas + detalles (trae las facturas), asigna y aprueba
    de forma sincrona. NO lanza el auto-rechazo aqui.

    Retorna {"created": [..], "approved": [..]}.
    """
    run_documenteme_stale_status_alerts()

    companies = frappe.get_all("Company", pluck="name")

    for company_id in companies:
        sync_by_supplier(
            supplier_id=company_id,
            get_tax_id_fn=get_company_tax_id,
            send_request_fn=send_request_status,
            create_log_fn=create_sync_log,
            create_lines_fn=create_sync_lines,
            commit_fn=lambda: frappe.db.commit(),
            nvfac_esta=nvfac_esta,
            nvfac_fini=nvfac_fini,
            nvfac_ffin=nvfac_ffin,
        )

    created_names = sync_detail(
        get_uncompleted_lines_fn=get_uncompleted_lines,
        send_request_fn=send_request_status,
        create_document_detail_fn=create_document_detail,
        log_sync_attempt_fn=log_sync_attempt,
        mark_line_completed_fn=mark_line_completed,
        commit_fn=lambda: frappe.db.commit(),
        get_company_tax_id_fn=get_log_company_tax_id,
    )

    created_names = created_names or []
    run_documenteme_auto_assign(doc_names or created_names)
    approve_result = run_documenteme_auto_approve(doc_names or created_names)

    return {
        "created": created_names,
        "approved": (approve_result or {}).get("approved") or [],
    }


def _launch_reject(doc_names):
    """Lanza el auto-rechazo EN SEGUNDO PLANO (job de fondo).

    Marcamos las facturas a rechazar como "P" (En proceso) de forma
    sincrona y encolamos el job. Aunque ya haya un job de rechazo en
    ejecucion, este llama encola con los documentos nuevos recibidos.
    """
    try:
        result = run_auto_reject(enqueue=True, doc_names=doc_names)
        frappe.db.commit()
        return result
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme auto_reject sync_all")
        return None


def run_documenteme_auto_assign(doc_names=None):
    try:
        run_auto_assign(doc_names=doc_names)
        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme auto_assign sync_all")


def run_documenteme_auto_reject(doc_names=None):
    return _launch_reject(doc_names)


def run_documenteme_auto_approve(doc_names=None):
    try:
        result = run_auto_approve(enqueue=False, doc_names=doc_names)
        frappe.db.commit()
        return result

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme auto_approve sync_all")
        return None


def run_documenteme_stale_status_alerts():
    try:
        generate_stale_status_alerts()
        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "documenteme stale_status_alerts sync_all")


@frappe.whitelist()
def sync_all(nvfac_esta=None, nvfac_fini=None, nvfac_ffin=None):
    """Sincronizacion programada (cron */30).

    La descarga de facturas es SINCRONA dentro del lock (para no pisar a
    otro cron en curso). Al final se lanza el auto-rechazo en segundo plano
    sobre las facturas nuevas.
    """
    nvfac_fini = nvfac_fini if nvfac_fini is not None else get_default_nvfac_fini()
    nvfac_ffin = nvfac_ffin if nvfac_ffin is not None else get_default_nvfac_ffin()

    if not sync_lock.acquire(DOCUMENTS_LOCK_DOMAIN):
        return {
            "success": False,
            "skipped": True,
            "error": "Ya hay una sincronización en curso",
        }

    try:
        sync_result = _sync_documents(
            nvfac_esta=nvfac_esta,
            nvfac_fini=nvfac_fini,
            nvfac_ffin=nvfac_ffin,
        )
        created_names = sync_result["created"]
        reject_result = _launch_reject(created_names)

        return {
            "success": True,
            "companies_count": len(frappe.get_all("Company", pluck="name")),
            "created_count": len(created_names),
            "rejected": (reject_result or {}).get("rejected") or [],
            "approved": sync_result["approved"],
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "sync_all")
        return {"success": False, "error": "Internal error"}
    finally:
        sync_lock.release(DOCUMENTS_LOCK_DOMAIN)


@frappe.whitelist()
def refresh_documents(nvfac_esta=None, nvfac_fini=None, nvfac_ffin=None):
    """Refresco manual (boton) — SIEMPRE trae facturas.

    Descarga de forma sincrona SIN tomar el lock global (para que, aunque
    el cron este corriendo, el usuario siempre pueda traer las facturas
    nuevas). Luego asigna, aprueba y lanza el auto-rechazo en segundo plano
    sobre las facturas nuevas.
    """
    try:
        sync_result = _sync_documents(
            nvfac_esta=nvfac_esta,
            nvfac_fini=nvfac_fini,
            nvfac_ffin=nvfac_ffin,
        )
        created_names = sync_result["created"]
        # Siempre lanza el rechazo en fondo (encola), aunque ya haya otro job.
        reject_result = _launch_reject(created_names)

        return {
            "success": True,
            "companies_count": len(frappe.get_all("Company", pluck="name")),
            "created_count": len(created_names),
            "rejected": (reject_result or {}).get("rejected") or [],
            "approved": sync_result["approved"],
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "refresh_documents")
        return {"success": False, "error": "Internal error"}
