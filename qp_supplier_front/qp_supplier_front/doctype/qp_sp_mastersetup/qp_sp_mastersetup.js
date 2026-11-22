// Copyright (c) 2025, Rafael Licett and contributors
// For license information, please see license.txt


frappe.ui.form.on('qp_SP_MasterSetup', {
	refresh: function(frm) {

		if (!frappe.user.has_role('Administrator')) {
			frm.toggle_display('documenteme_simulation', false);
		}

		if (!(frm.is_new())){

				frm.add_custom_button(__('Facturas'), function() {
					let method = 'qp_supplier_front.services.clean_table.invoice';

					let message = `Tabla de Facturas han sido limpiada correctamente`;

					sync(null, method, message)				}, __("Limpiar Tablas"));
				frm.add_custom_button(__('Ordenes'), function() {
					let method = 'qp_supplier_front.services.clean_table.order';

					let message = `Tabla de Ordenes han sido limpiada correctamente`;

					sync(null, method, message)
				}, __("Limpiar Tablas"));

				frm.add_custom_button(__('Pagos'), function() {

					let method = 'qp_supplier_front.services.clean_table.receipt';

					let message = `Tabla de Pagos han sido limpiada correctamente`;

					sync(null, method, message)

				}, __("Limpiar Tablas"));

				frm.add_custom_button(__('Todos'), function() {

					let method = 'qp_supplier_front.services.clean_table.all';

					let message = `Todas las tablas han sido limpiada correctamente`;

					sync(null, method, message)

				}, __("Limpiar Tablas"));

				frm.add_custom_button(__('Proveedores'), function() {
					if (!frm.is_dirty()){
						sync_customer(frm, frm.doc.name)
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
				}, __("Sincronizar"));

				frm.add_custom_button(__('Recibos'), function() {
					if (!frm.is_dirty()){
						sync(frm.doc.name, 'qp_supplier_front.uses_cases.payment_receipt.sync_by_supplier.sync_full',
							`Sincronización general de recibos ejecutada en segundo plano, revise el Sync Log`);
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
				}, __("Sincronizar"));

				frm.add_custom_button(__('Facturas'), function() {
					if (!frm.is_dirty()){
						sync(frm.doc.name, 'qp_supplier_front.uses_cases.purchase_invoice.sync_by_supplier.sync_full',
							`Sincronización general de facturas ejecutada en segundo plano, revise el Sync Log`);
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
				}, __("Sincronizar"));

				frm.add_custom_button(__('Productos'), function(){
					if (!frm.is_dirty()){
						sync_items(frm, frm.doc.name)
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
					
				}, __("Sincronizar"));
				frm.add_custom_button(__('Todo'), function(){
					if (!frm.is_dirty()){
						sync_all(frm, frm.doc.name)
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
					
				}, __("Sincronizar"));

				frm.add_custom_button(__('Documenteme por rango'), function(){
					open_documenteme_range_dialog()
				}, __("Sincronizar"));

		}
	}
});

var DOCUMENTEME_MAX_RANGE_DAYS = 90;
var URL_SYNC_DOCUMENTEME_RANGE = 'qp_supplier_front.uses_cases.documents.sync_all_whitelist.sync_by_date_range';

function open_documenteme_range_dialog(){
	let today = frappe.datetime.get_today();

	let dialog = new frappe.ui.Dialog({
		title: __('Sincronizar Documenteme por rango de fechas'),
		fields: [
			{
				fieldname: 'fecha_inicio',
				fieldtype: 'Date',
				label: __('Fecha de inicio'),
				reqd: 1
			},
			{
				fieldname: 'fecha_fin',
				fieldtype: 'Date',
				label: __('Fecha de fin'),
				default: today,
				reqd: 1
			},
			{
				fieldtype: 'HTML',
				fieldname: 'rango_ayuda',
				options: '<p class="text-muted small">' +
					__('Máximo {0} días. La fecha de fin no puede superar hoy.', [DOCUMENTEME_MAX_RANGE_DAYS]) +
					'</p>'
			}
		],
		primary_action_label: __('Sincronizar'),
		primary_action: function(values){
			let error = validate_documenteme_range(values.fecha_inicio, values.fecha_fin);
			if (error){
				frappe.msgprint({
					title: __('Rango inválido'),
					message: error,
					indicator: 'red'
				});
				return;
			}
			dialog.hide();
			sync_documenteme_range(values.fecha_inicio, values.fecha_fin);
		}
	});

	dialog.show();
	apply_documenteme_date_limits(dialog);
}

// Restringe el calendario y limpia la fecha de fin si queda fuera del rango.
function apply_documenteme_date_limits(dialog){
	let today = moment(frappe.datetime.get_today(), 'YYYY-MM-DD');
	let start_control = dialog.fields_dict.fecha_inicio;
	let end_control = dialog.fields_dict.fecha_fin;

	if (!start_control || !start_control.datepicker || !end_control || !end_control.datepicker){
		return;
	}

	start_control.datepicker.update({ maxDate: today.toDate() });
	end_control.datepicker.update({ maxDate: today.toDate() });

	start_control.$input.on('change', function(){
		let start_value = dialog.get_value('fecha_inicio');
		if (!start_value){
			return;
		}

		let start = moment(start_value, 'YYYY-MM-DD');
		let max_date = start.clone().add(DOCUMENTEME_MAX_RANGE_DAYS - 1, 'days');
		if (max_date.isAfter(today)){
			max_date = today.clone();
		}

		end_control.datepicker.update({
			minDate: start.toDate(),
			maxDate: max_date.toDate()
		});

		let end_value = dialog.get_value('fecha_fin');
		if (end_value && validate_documenteme_range(start_value, end_value)){
			dialog.set_value('fecha_fin', '');
		}
	});
}

function validate_documenteme_range(fecha_inicio, fecha_fin){
	if (!fecha_inicio || !fecha_fin){
		return __('Debe indicar la fecha de inicio y la fecha de fin');
	}
	if (fecha_inicio > fecha_fin){
		return __('La fecha de inicio no puede ser mayor que la fecha de fin');
	}
	if (fecha_fin > frappe.datetime.get_today()){
		return __('La fecha de fin no puede ser mayor que hoy');
	}
	if (frappe.datetime.get_diff(fecha_fin, fecha_inicio) + 1 > DOCUMENTEME_MAX_RANGE_DAYS){
		return __('El rango de fechas no puede superar los {0} días', [DOCUMENTEME_MAX_RANGE_DAYS]);
	}
	return null;
}

function sync_documenteme_range(fecha_inicio, fecha_fin){
	frappe.call({
		method: URL_SYNC_DOCUMENTEME_RANGE,
		args: {
			fecha_inicio: fecha_inicio,
			fecha_fin: fecha_fin
		},
		freeze: true,
		freeze_message: __('Sincronizando facturas de Documenteme...'),
		callback: function(r){
			if (r.exc){
				return;
			}
			show_documenteme_range_result(r.message || {});
		}
	});
}

function show_documenteme_range_result(result){
	if (result.skipped){
		frappe.msgprint({
			title: __('Sincronización en curso'),
			message: result.error || __('Ya hay una sincronización en curso'),
			indicator: 'orange'
		});
		return;
	}
	if (result.success === false){
		frappe.msgprint({
			title: __('No se pudo sincronizar'),
			message: result.error || __('Error interno'),
			indicator: 'red'
		});
		return;
	}
	frappe.msgprint({
		title: __('Sincronización completada'),
		message: __('Facturas sincronizadas: {0}', [result.created_count || 0]),
		indicator: 'green'
	});
}

function sync_customer(frm, master_name){

	let method = 'qp_supplier_front.uses_cases.supplier.sync_all.handler';

	let message = `Esta sincronización se ejecuta en segundo plano, para mas informacion consulte el Item Sync Log : `;

	sync(master_name, method, message)

}
function sync_items(frm, master_name){

	let method = 'qp_supplier_front.uses_cases.item.sync_all.handler';

	let message = `Esta sincronización se ejecuta en segundo plano, para mas informacion consulte el Item Sync Log : `;

	sync(master_name, method, message)

}

function sync_all(frm, master_name){

	let method = 'qp_supplier_front.taks.sync.all';

	let message = `Sincronizacion finalizada, revise el registro de errores para verificar que culmino exitosamente `;

	sync(master_name, method, message)

}

function sync(master_name, method, message){

	frappe.call({
		method,
		callback: function(r) {
			if (!r.exc) {

				
				frappe.msgprint({
					message: message,
					indicator: 'green',
					title: __('Success')
				});
			}
		},
		freeze:true

	});
}
