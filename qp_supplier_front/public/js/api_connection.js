
API_ROOT = "qp_phonix_front.resources"

//function petition_get_data(args, method, callresponse = null) {
//
//    frappe.call({
//        method: method,
//        args: args,
//        callback: function (r) {
//            // ÉXITO (HTTP 200)
//            let data = r.message;
//            if (callresponse) {
//                callresponse(data);
//            }
//            resolve(data);
//        },
//        error: function (r) {
//            // ERROR (Captura el frappe.throw / HTTP 417 o 500)
//            let error_msg = "Error en el servidor";
//
//            if (r._server_messages) {
//                // Frappe guarda los mensajes del throw aquí
//                let msgs = JSON.parse(r._server_messages);
//                error_msg = JSON.parse(msgs[0]).message;
//            }
//
//            // Creamos un objeto de error con el formato que esperas
//            let error_obj = {
//                status: 400, // Forzamos un status para tu lógica
//                error: true,
//                msg: error_msg,
//                raw: r
//            };
//
//            if (callresponse) {
//                // Ejecutamos tu acción de callback incluso en error
//                callresponse(error_obj);
//            }
//
//            reject(error_obj);
//        }
//    });
//
//}
function petition_get_data(args, method, callresponse = null) {
    frappe.call({
        method,
        type: "POST",
        args,
        callback: function (r) {
            if (callresponse) {
                callresponse(r.message);
            }
        },
        freeze: true,
        freeze_message: "Esperando",
        async: true
    }).fail(function(xhr, textStatus, errorThrown) {
        if (callresponse) {
            var error_msg = "Error en el servidor";
            var response_data = null;
            if (xhr && xhr.responseJSON && xhr.responseJSON.message) {
                error_msg = xhr.responseJSON.message.msg || error_msg;
                response_data = xhr.responseJSON.message.data || null;
            }
            callresponse({status: (xhr && xhr.status) || 400, error: true, msg: error_msg, data: response_data});
        }
    });
}
function petition_send_data(formData, method, callback, request = "POST") {

    return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();
        xhr.onreadystatechange = () => {
            if (xhr.readyState == XMLHttpRequest.DONE) {
                response = JSON.parse(xhr.responseText);

                if (xhr.status === 200) {
                    callback(response.message);
                } else {
                    callback(response.message);
                    frappe.msgprint(__(`Error: ${response.message.msg}`));
                }
            }
        }
        console.log(request, method)
        xhr.open(request, method, true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
        xhr.send(formData);
    })
}