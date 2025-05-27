// Copyright (c) 2025, Rafael Licett and contributors
// For license information, please see license.txt


frappe.ui.form.on('qp_SP_MasterSetup', {
	refresh: function(frm) {

		if (!(frm.is_new())){

				frm.add_custom_button(__('Proveedores'), function(){
					if (!frm.is_dirty()){
						sync_customer(frm, frm.doc.name)
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
					
				});
				frm.add_custom_button(__('Crear Productos'), function(){
					if (!frm.is_dirty()){
						sync_items(frm, frm.doc.name)
					}
					else{
						show_alert (__("Unable to sync, <br> There are unsaved changes"))
					}
					
				});

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
function sync(master_name, method, message){

	frappe.call({
		method,
		callback: function(r) {
			if (!r.exc) {

				/*const response = r.message
				
				if (response.has_pending){
					message = `Existe una sincronización en proceso`

				}*/
				
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
