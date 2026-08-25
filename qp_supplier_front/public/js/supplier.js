frappe.ui.form.on("Supplier", {
    refresh: function(frm) {
        // Roles permitidos para editar el DocType en el desk.
        // Se puede agregar "Alpla Administrator", "Alpla Compras", "Alpla Finanzas" en esta lista si es necesario.
        const allowed_roles = ["Administrator"];

        // Verificar si el usuario tiene al menos uno de los roles permitidos
        const has_write_permission = allowed_roles.some(role => frappe.user_roles.includes(role));

        if (!has_write_permission) {
            frm.disable_form();
        }
    }
});
