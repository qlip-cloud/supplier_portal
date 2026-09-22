frappe.ui.form.on("Supplier", {
    refresh: function(frm) {
        // Roles permitidos para editar todos los campos del DocType en el desk.
        // Se puede agregar "Alpla Administrator", "Alpla Compras", "Alpla Finanzas" en esta lista si es necesario.
        const allowed_roles = ["Administrator", "System Manager"];

        // Roles con acceso parcial: solo pueden modificar la configuracion de
        // documenteme del proveedor (Proveedor de servicio y Rechazo automatico).
        const documenteme_roles = ["Administrador Documenteme"];

        // Campos editables por los roles con acceso parcial de documenteme.
        const documenteme_fields = ["qp_is_service_supplier", "auto_reject"];

        const has_role = (roles) => roles.some(role => frappe.user_roles.includes(role));

        // Verificar si el usuario tiene al menos uno de los roles permitidos
        const has_write_permission = has_role(allowed_roles);

        if (has_write_permission) {
            return;
        }

        // Rol de documenteme: habilita solo los campos de configuracion asignados.
        const has_documenteme_permission = has_role(documenteme_roles);

        if (has_documenteme_permission) {
            frm.fields.forEach(function(field) {
                const fieldname = field.df.fieldname;
                const editable = documenteme_fields.includes(fieldname);
                frm.set_df_property(fieldname, "read_only", editable ? 0 : 1);
            });
            return;
        }

        frm.disable_form();
    }
});