def assign_documents(sync_line_names, user, get_doc_fn, save_fn):
    for line_name in sync_line_names:
        line = get_doc_fn("qp_SP_DocumentSyncLine", line_name)
        line.assigned_to = user
        save_fn(line)
