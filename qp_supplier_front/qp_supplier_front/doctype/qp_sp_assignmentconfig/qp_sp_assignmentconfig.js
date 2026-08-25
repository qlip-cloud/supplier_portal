// Copyright (c) 2026, Rafael Licett and contributors
// For license information, please see license.txt

frappe.ui.form.on('qp_SP_AssignmentConfig', {
	refresh: function(frm) {
		frappe.call({
			method: 'qp_supplier_front.qp_supplier_front.doctype.qp_sp_assignmentconfig.qp_sp_assignmentconfig.get_assignment_config_options',
			callback: function(response) {
				var options = response.message || {};
				var sedes = (options.sedes || []).map(function(s) {
					return s.value + '\n' + s.label;
				});
				frm.set_df_property('headquarter', 'options', sedes);
				frm.set_df_property('oc_type', 'options', options.oc_types || []);
				frm.refresh_fields();
			}
		});
	}
});
