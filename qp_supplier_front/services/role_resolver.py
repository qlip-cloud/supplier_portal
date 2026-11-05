ROLE_PRIORITY = [
    "Administrador Sede Documenteme",
    "Administrador Compras Documenteme",
    "Administrador Documenteme",
]

ADMIN_EQUIVALENT = "Administrador Documenteme"


def get_active_role(user_roles):
    active = None
    for role in ROLE_PRIORITY:
        if role in user_roles:
            active = role
    if active is None and "Administrator" in user_roles:
        active = ADMIN_EQUIVALENT
    return active


def has_any_documenteme_role(user_roles):
    return get_active_role(user_roles) is not None


def update_website_context(context):
    import frappe

    user_roles = frappe.get_roles()
    context["is_documenteme_admin"] = has_any_documenteme_role(user_roles)
