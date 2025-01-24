function showTab(tabId) {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');
    const form = document.getElementById('dynamicForm');

    // Remove active class from all tabs and hide all tab contents
    tabs.forEach(tab => tab.classList.remove('active'));
    contents.forEach(content => content.style.display = 'none');

    // Add active class to the clicked tab and show the corresponding tab content
    const activeTab = document.querySelector(`[onclick="showTab('${tabId}')"]`);
    const activeContent = document.getElementById(tabId);

    activeTab.classList.add('active');
    activeContent.style.display = 'block';

    // Move the form to the active tab content
}

document.addEventListener('DOMContentLoaded', function() {
    const dropdown = document.getElementById('dropdown');
    const tabs = document.querySelectorAll('.tab-content');

    dropdown.addEventListener('change', function() {
        tabs.forEach(tab => tab.style.display = 'none');
        document.getElementById(this.value).style.display = 'block';
    });
});

$(document).ready(function () {
    showTab('tab1');

    $('.form-estandar').on('submit', function (event) {

        event.preventDefault(); // Evita el envío del formulario
        var formData = new FormData(this);

        supplier_id = $("#supplier_id").val();

        formData.append("supplier_id",supplier_id);

        callresponse = (response) =>{
            
            frappe.msgprint(response.msg)
            if ($(this).hasClass("form-modal")) {
                $('.modal').modal('hide')

            }

        }


        petition_send_data(formData, $(this).attr('action'), callresponse)

    });
    
    $('#form-document').on('submit', function (event) {

        event.preventDefault(); // Evita el envío del formulario

        var data = {"documents": {}};

        $('#form-document input[data-document]').each(function() {
            var docType = $(this).data('document');
            var name = $(this).attr('name');
            var value = $(this).val();

            if (!data["documents"][docType]) {
                data["documents"][docType] = {};
            }

            data["documents"][docType][name] = value;
        });

        var supplier_id = $("#supplier_id").val();

        data["supplier_id"] = supplier_id;


        callresponse = (response) =>{

            frappe.msgprint(response.msg)

        }

        petition_get_data(data, $(this).attr('action'), callresponse)

    });
    
    
    $("#link").on("click", function () {
        setting_id = $(this).data("setting-id");
        document.getElementById(`file-${setting_id}`).click()
    })

    $(".supplier_file").on("change", function () {

        $("#file_empty").hide()

        $("#file_loading").show()

        supplier_id = $("#supplier_id").val();
        setting_id = $(this).data("setting-id");

        fileToUpload = $(this).prop('files');

        var formData = new FormData();

        url = "/api/method/upload_file"

        formData.append("file", fileToUpload[0], fileToUpload[0].name);

        formData.append("is_private", 0);

        formData.append("doctype", "Supplier");

        formData.append("docname", supplier_id);

        formData.append("fieldname", fileToUpload[0].name);

        callback = (status, data) => {

            if (status == 200) {

                $("#file_loading").hide()               
                $(`#file_full-${setting_id} a`).attr('href', data.file_url);
                $(`#file_full-${setting_id} a`).html(data.file_name)
                $(`#file1-${setting_id}`).val(data.file_url)
                $(`#file_full-${setting_id}`).show()


            } else {
                $("#file_empty").show()
                $("#file_loading").hide()
            }

        }
        method = "/api/method/upload_file"

        send_upload(method, formData, callback)

    })
});


function send_upload(method, formData, callresponse){

    return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();

        xhr.onreadystatechange = () => {
            if (xhr.readyState == XMLHttpRequest.DONE) {

                response = JSON.parse(xhr.responseText)

                var message = response.message

                if (callresponse) {
    
                    callresponse(xhr.status, message)
    
                }     
            }
        }
        
        xhr.open('POST',method , true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
        xhr.send(formData);

    })
}