// Copyright (c) 2025, Rafael Licett and contributors
// For license information, please see license.txt


frappe.ui.form.on('qp_SP_MasterSetup', {
	refresh: function(frm) {

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

		}
	}
});

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
