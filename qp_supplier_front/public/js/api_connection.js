
API_ROOT = "qp_phonix_front.resources"

async function petition_get_data(args, method, callresponse = null){

    //console.log(payload, module_root, method)

    return new Promise(() => {
        frappe.call({
            method,
            args,
            async: false,
            callback: function (xhr) {

                response = xhr.message

                if (response.status == 200) {

                    if (callresponse) {

                        callresponse(response)

                    }
                }

                if (response.status == 400) {

                    if (callresponse) {

                        callresponse(response.data)

                    }
                    frappe.msgprint(__(`error: ${response.msg}`))
                }

                if (response.status == 500) {

                    if (callresponse) {

                        callresponse(response)

                    }
                }


            }
        })
    })
    
}

function petition_send_data(formData, method, callback, request = "POST"){

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
        xhr.open(request,method , true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
        xhr.send(formData);
    })
}