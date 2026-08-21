"""
documenteme_access.py
=====================
Control de acceso a las facturas del portal documenteme segun el rol
del usuario autenticado.

Roles que ven TODAS las facturas:
  - Administrator (equivalente a Administrador Documenteme)
  - Administrador Documenteme
  - Administrador Compras Documenteme

Rol restringido (solo ve las facturas que tiene asignadas):
  - Administrador Sede Documenteme

La deteccion del rol se hace por la lista de roles de frappe (frappe.get_roles()).
La asignacion de una factura al usuario se resuelve a partir de
qp_SP_SyncLineAssignedUser (hijo) y del campo assigned_to de
qp_SP_DocumentSyncLine. El filtro resultante se aplica sobre el campo
"nvfac_nume" de qp_SP_DocumentDetail (que coincide con el name de la
sync line).

Funciones sin import a Frappe en la firma para facilitar el testeo.
"""

ROLE_ADMIN_DOCUMENTEME = "Administrador Documenteme"
ROLE_COMPRAS_DOCUMENTEME = "Administrador Compras Documenteme"
ROLE_SEDE_DOCUMENTEME = "Administrador Sede Documenteme"

SEE_ALL_ROLES = ("Administrator", ROLE_ADMIN_DOCUMENTEME, ROLE_COMPRAS_DOCUMENTEME)


def can_see_all_documenteme(user_roles):
    """True si el usuario tiene un rol que ve todas las facturas."""
    return any(role in (user_roles or []) for role in SEE_ALL_ROLES)


def is_sede_documenteme(user_roles):
    """True si el usuario es Administrador Sede Documenteme restringido.

    Un usuario con rol sede pero que tambien tiene un rol de vision total
    (admin/compras) ve todas las facturas y conserva los botones de
    asignacion, por lo que no se considera restringido.
    """
    roles = list(user_roles or [])
    return ROLE_SEDE_DOCUMENTEME in roles and not can_see_all_documenteme(roles)


def get_assigned_sync_lines_filters(
    user_roles, user, assigned_line_names_fn, filters=None
):
    """Devuelve los filters con la restriccion por asignacion.

    - Si el usuario ve todas las facturas, devuelve filters sin cambios.
    - Si no, agrega un filtro "nvfac_nume" in sobre las sync lines que
      tiene asignadas el usuario (via child rows o assigned_to).
    """
    result = dict(filters or {})

    if can_see_all_documenteme(user_roles):
        return result

    assigned = assigned_line_names_fn(user)
    if assigned:
        result["nvfac_nume"] = ["in", assigned]
    else:
        result["nvfac_nume"] = ["in", []]

    return result


def get_assigned_sync_line_names(user):
    """Retorna los nombres de qp_SP_DocumentSyncLine asignados al usuario.

    Incluye las sync lines donde el usuario aparece en el child table
    qp_SP_SyncLineAssignedUser y las donde es assigned_to directo.
    """
    import frappe

    names = set()

    child_rows = frappe.get_all(
        "qp_SP_SyncLineAssignedUser",
        filters={"user": user, "parenttype": "qp_SP_DocumentSyncLine"},
        fields=["parent"],
    )
    for row in child_rows:
        names.add(row.get("parent"))

    direct_rows = frappe.get_all(
        "qp_SP_DocumentSyncLine",
        filters={"assigned_to": user},
        fields=["name"],
    )
    for row in direct_rows:
        names.add(row.get("name"))

    return list(names)
