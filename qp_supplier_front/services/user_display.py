# -*- coding: utf-8 -*-
"""
user_display.py
===============
Regla de presentacion para usuarios asignados (documenteme y collection).

Si el usuario no tiene apellido (su `full_name` es una sola palabra) o no
tiene nombre, se muestra su identificador (correo) para no mostrar un nombre
incompleto. Con nombre y apellido se muestra el `full_name` normalizado.
"""


def resolve_user_display_name(full_name, user_id):
    """Nombre visible de un usuario asignado.

    - Con apellido (dos o mas palabras): `full_name` normalizado.
    - Sin apellido / vacio: `user_id` (el correo), para no mostrarlo incompleto.
    """
    name = " ".join((full_name or "").split())
    if not name or " " not in name:
        return user_id
    return name
