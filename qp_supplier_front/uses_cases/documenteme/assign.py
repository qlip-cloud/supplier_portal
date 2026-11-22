def _normalize_users(users):
    """Lista de usuarios unicos y no vacios, en el orden recibido."""
    unique = []
    for user in (users or []):
        if not user:
            continue
        if user not in unique:
            unique.append(user)
    return unique


def assign_documents(sync_line_names, users, get_doc_fn, save_fn):
    """Asigna la factura a uno o varios usuarios (reemplaza la asignacion).

    Escribe el child `assigned_users` (mismo destino que la asignacion
    automatica) y limpia el campo legacy `assigned_to` para que no quede un
    asignado anterior visible.

    Retorna la lista normalizada de usuarios asignados.
    """
    normalized = _normalize_users(users)

    for line_name in sync_line_names:
        line = get_doc_fn("qp_SP_DocumentSyncLine", line_name)
        line.assigned_to = None
        line.set("assigned_users", [
            {"user": user} for user in normalized
        ])
        save_fn(line)

    return normalized
