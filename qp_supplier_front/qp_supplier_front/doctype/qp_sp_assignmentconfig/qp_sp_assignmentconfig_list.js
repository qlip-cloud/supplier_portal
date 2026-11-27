// Copyright (c) 2026, Rafael Licett and contributors
// For license information, please see license.txt

frappe.listview_settings['qp_SP_AssignmentConfig'] = {
	onload: function(listview) {
		frappe.call({
			method: 'qp_supplier_front.qp_supplier_front.doctype.qp_sp_assignmentconfig.qp_sp_assignmentconfig.get_assignment_config_options',
			callback: function(response) {
				var options = response.message || {};
				apply_standard_filter_options(listview, 'headquarter', options.sedes || []);
				apply_standard_filter_options(listview, 'oc_type', options.oc_types || []);
			}
		});
	}
};

// Populates the standard list filters (Sede / OC Type) with the dynamic
// options. These fields are Select with empty static options in the doctype,
// so the list builds empty dropdowns unless we feed them at runtime.
function apply_standard_filter_options(listview, fieldname, field_options) {
	var fields_dict = listview.page && listview.page.fields_dict;
	var field = fields_dict && fields_dict[fieldname];

	if (field && field.set_options) {
		// First empty-value option resets the filter and shows every row again.
		var options = [{ value: "", label: __("Todos") }].concat(field_options);
		field.df.options = options;
		field.set_options();
		if (field.toggle_placeholder) {
			field.toggle_placeholder();
		}
	}

	// Keep the meta in sync so the "Add filter" popover also offers the
	// options. Stored as a plain value list to stay compatible with the
	// Select filter config that expects a newline string.
	var meta_df = frappe.meta.get_docfield('qp_SP_AssignmentConfig', fieldname);
	if (meta_df) {
		meta_df.options = field_options
			.map(function(option) { return option.value; })
			.join('\n');
	}
}
