from qp_supplier_front.uses_cases.documenteme.event_notifier import send_event_sequence


def reject_document(doc_name, motive, is_invoice_error,
                    get_doc_fn, send_request_fn, commit_fn,
                    get_company_tax_id_fn, now_fn):
    doc = get_doc_fn("qp_SP_DocumentDetail", doc_name)

    if is_invoice_error:
        event_config = {
            "031": {"nvfac_esta": "R"},
        }
        send_event_sequence(
            doc, event_config, send_request_fn, commit_fn,
            get_company_tax_id_fn, now_fn,
            required_nvfac_esta="E",
        )
        doc.qp_is_event_completed = 1
        doc.nvfac_ueve = "031"

    doc.nvfac_esta = "R"
    doc.qp_motive = motive
    doc.save()
    commit_fn()

    return doc