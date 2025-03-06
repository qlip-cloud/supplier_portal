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

document.addEventListener('DOMContentLoaded', function () {
    const dropdown = document.getElementById('dropdown');
    const tabs = document.querySelectorAll('.tab-content');

    dropdown.addEventListener('change', function () {
        tabs.forEach(tab => tab.style.display = 'none');
        document.getElementById(this.value).style.display = 'block';
    });
});

$(document).ready(function () {
    showTab('tab1');

    $("#tax_id").on("blur", function(){

    
        tax_id = $(this).val()

        url = "qp_supplier_front.resources.supplier.supplier.find";

        callresponse = (response) => {
            
            supplier = response.data
            if (supplier){
                if (supplier.qp_asigned){
                    frappe.msgprint("Ya este proveedor esta registrado en el sistema")
                    $("#save").hide();
                    $("#supplier_name").val()
                    $(this).val()

                }else{

                    $("#supplier_name").val(supplier.supplier_name)
                }
            }else{
                $("#supplier_name").val()

                $("#save").show()

            }
            


        }


        petition_get_data({ tax_id }, url, callresponse)
    
    })

    $('.form-estandar').on('submit', function (event) {


        event.preventDefault(); // Evita el envío del formulario

        var formData = new FormData(this);

        supplier_id = $("#supplier_id").val();

        formData.append("supplier_id", supplier_id);

        const submitter = $(document.activeElement);
        if (submitter.hasClass('is_estatus_editable') || $(this).hasClass("form-modal")) {

            document.getElementById("overlay").style.display = 'block';

            callresponse = (response) => {

                data = response.data
                //frappe.msgprint(response.msg)

                if (data.redirect_to) {
                    window.location.href = data.redirect_to
                }

                if ($(this).hasClass("form-modal")) {

                    $('.modal').modal('hide')

                    if (data.render) {

                        render = data.render
    
                        $(`#${render.container}`).html(render.list)
                    }

                }else{
                    if (!$(this).hasClass("form-modal")){

                        showTab(submitter.data("control"))
                    }
                }

                $(this).attr('method', $(this).data("method-default"));               

                document.getElementById("overlay").style.display = 'none';

            }

            petition_send_data(formData, $(this).attr('action'), callresponse, $(this).attr('method'))
        } else {
            showTab(submitter.data("control"))

        }
    });

    $('#form-document').on('submit', function (event) {

        event.preventDefault(); // Evita el envío del formulario

        var data = { "documents": {} };

        $('#form-document .file-link').each(function () {
            if ($(this).data('updated') == "1") {
                var docType = $(this).data('document');
                var name = $(this).attr('name');
                var value = $(this).val();

                if (!data["documents"][docType]) {
                    data["documents"][docType] = {};
                }

                data["documents"][docType][name] = value;
            }
        });

        var supplier_id = $("#supplier_id").val();

        data["supplier_id"] = supplier_id;
        
        const submitter = $(document.activeElement);

        data["is_estatus_editable"] = submitter.hasClass('is_estatus_editable');

        if (submitter.hasClass('is_estatus_editable') || submitter.hasClass('finish')) {

            document.getElementById("overlay").style.display = 'block';

            callresponse = (response) => {

                data = response.data

                if (submitter.hasClass("finish")) {

                    frappe.msgprint(response.msg)

                    setup_button(data.supplier)

                }
                if (submitter.hasClass('is_estatus_editable') ){

                    showTab(submitter.data("control"))
                }
                document.getElementById("overlay").style.display = 'none';

            }

            petition_get_data(data, $(this).attr('action'), callresponse)
        } else {
            showTab(submitter.data("control"))

        }

    });
    

    $(".open_folder").on("click", function () {

        setting_id = $(this).data("setting-id");

        document.getElementById(`file-${setting_id}`).click()
    })

    $("#approve").on("click", function () {

        frappe.confirm('¿Seguro que desea aprobar el registro?',
            function () {

                supplier_id = $("#supplier_id").val();

                url = "qp_supplier_front.resources.supplier.supplier.approve";

                callresponse = (response) => {

                    frappe.msgprint(response.msg)

                    data = response.data

                    setup_button(data.supplier)
                    
                    $(".approve-row").remove()
                }


                petition_get_data({ supplier_id }, url, callresponse)


            }, function () { })
    })

    $('#qp_reject_observation').on('input', function () {
        if ($(this).val().trim() !== '') {
            $('#reject').prop('disabled', false);
        } else {
            $('#reject').prop('disabled', true);
        }
    });


    $("#reject").on("click", function () {
        supplier_id = $("#supplier_id").val();

        qp_reject_observation = $("#qp_reject_observation").val();

        url = "qp_supplier_front.resources.supplier.supplier.reject";

        callresponse = (response) => {

            frappe.msgprint(response.msg)

            $('.modal').modal('hide')

            data = response.data
            console.log(data.supplier)
            setup_button(data.supplier)
            $(".approve-row").remove()

        }


        petition_get_data({ supplier_id, qp_reject_observation }, url, callresponse)


    })
    $("#country").on("change", function () {

        country = $(this).val();

        url = "qp_supplier_front.resources.information.address.search_cities";

        callresponse = (response) => {
            data = response.data

            cities_list = data.cities

            setOptionCities(cities_list)

        }

        petition_get_data({ country }, url, callresponse)

    })

    $("#city").on("change", function () {

        city = $(this).val();

        url = "qp_supplier_front.resources.information.address.search_states";

        callresponse = (response) => {

            data = response.data

            states_list = data.states

            setOptionStates(states_list)

        }

        petition_get_data({ city }, url, callresponse)

    })

    $("#address_list").on("click", ".addres-id", function () {

        address_id = $(this).data("id");

        url = "qp_supplier_front.resources.information.address.search_address";

        callresponse = (response) => {
            const data = response.data
            const address = data.address
            const cities = data.cities
            const states = data.states
            const $doctype_id = $("#form-address [name='doctype_id']");
            const $selectCountry = $("#country");
            const $selectCity = $("#city");
            const $selectState = $("#state");
            const $selectAddress_line1 = $("#address_line1");


            setOptionCities(cities)

            setOptionStates(states)

            $doctype_id.val(address_id);

            $selectCountry.val(address.country);

            $selectCity.val(address.city);

            $selectState.val(address.state);

            $selectAddress_line1.val(address.address_line1);

            $("#form-address").attr('method', 'PUT');
            $('#addres_modal').modal('show')
        }

        petition_get_data({ address_id }, url, callresponse)
    })

    $("#contact_list").on("click", ".contact-id", function () {

        contact_id = $(this).data("id");

        url = "qp_supplier_front.resources.information.contact.search_contact";

        callresponse = (response) => {

            const data = response.data
            const contact = data.contact
            const $doctype_id = $("#form-contact [name='doctype_id']");
            const $dataFirstName = $("#first_name");
            const $dataEmailId = $("#email_id");
            const $dataPhone = $("#phone");

            $doctype_id.val(contact_id);

            $dataFirstName.val(contact.first_name);

            $dataEmailId.val(contact.email_ids[0].email_id);

            $dataPhone.val(contact.phone_nos.length ? contact.phone_nos[0].phone : "");

            $("#form-contact").attr('method', 'PUT');
            $('#contact_modal').modal('show')
        }

        petition_get_data({ contact_id }, url, callresponse)
    })

    $("#bank_account_list").on("click", ".bank_account-id", function () {

        bank_account_id = $(this).data("id");

        url = "qp_supplier_front.resources.information.bank_account.search_bank_account";

        callresponse = (response) => {
            const data = response.data
            const bank_account = data.bank_account
            console.log(bank_account)
            const $doctype_id = $("#form-bank-account [name='doctype_id']");

            const $selectBank = $("#bank");
            const $selectAccountType = $("#account_type");
            const $dataBankAccount_no = $("#bank_account_no");

            $doctype_id.val(bank_account_id);

            $selectBank.val(bank_account.bank);

            $selectAccountType.val(bank_account.account_type);

            $dataBankAccount_no.val(bank_account.bank_account_no);

            $("#form-bank-account").attr('method', 'PUT');
            $('#bank_account_modal').modal('show')
        }

        petition_get_data({ bank_account_id }, url, callresponse)
    })

    $("#shareholder_list").on("click", ".shareholder-id", function () {

        shareholder_id = $(this).data("id");

        url = "qp_supplier_front.resources.information.shareholder.search_shareholder";

        callresponse = (response) => {
            const data = response.data
            const shareholder = data.shareholder
            const $doctype_id = $("#form-shareholder [name='doctype_id']");
            const $dataFulname = $("#fullname");
            const $dataNationality = $("#nationality");
            const $selectHaveResidentAnotherCountry = $("#have_resident_another_country");
            const $selectHaveAmericanVisa = $("#have_american_visa");
            const $selectIdType = $("#id_type");
            const $dataTaxId = $("#tax_id");
            const $dataMarketShare = $("#market_share");
            const $selectAuthorizationDataProcessing = $("#authorization_data_processing");
            const $selectSupplierCodeConduct = $("#supplier_code_conduct");


            $doctype_id.val(shareholder_id);

            $dataFulname.val(shareholder.fullname);
            $dataNationality.val(shareholder.nationality);
            $selectHaveResidentAnotherCountry.val(shareholder.have_resident_another_country);
            $selectHaveAmericanVisa.val(shareholder.have_american_visa);
            $selectIdType.val(shareholder.id_type);
            $dataTaxId.val(shareholder.tax_id);
            $dataMarketShare.val(shareholder.market_share);
            $selectAuthorizationDataProcessing.val(shareholder.authorization_data_processing);
            $selectSupplierCodeConduct.val(shareholder.supplier_code_conduct);

            $("#form-shareholder").attr('method', 'PUT');
            $('#shareholder_modal').modal('show')
        }

        petition_get_data({ shareholder_id }, url, callresponse)
    })

    $(".supplier_file").on("change", function () {
        supplier_id = $("#supplier_id").val();

        setting_id = $(this).data("setting-id");

        $(`#file_empty-${setting_id}`).hide()

        $(`#file_loading-${setting_id}`).show()

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
                
                $(`#file_loading-${setting_id}`).hide()
                $(`#file_full-${setting_id} a`).attr('href', data.file_url);
                $(`#file_full-${setting_id} a`).html("Ver archivo")
                $(`#link-${setting_id}`).val(data.file_url)
                $(`#link-${setting_id}`).attr("data-updated", "1")
                $(`#file_full-${setting_id}`).show()
                $(`#file_full-${setting_id}`).show()

            } else {
                $(`#file_empty-${setting_id}`).show()
                $(`#file_loading-${setting_id}`).hide()
            }

        }
        method = "/api/method/upload_file"

        send_upload(method, formData, callback)

    })
});

function setup_button(supplier) {

    const alert_estatus = {
        "En proceso": {
            "class": "alert-info",
            "message": "El proceso de registro esta en estatus: <strong>En proceso</strong>. Por favor llenar todos los datos."
        },
        "Aprobado": {
            "class": "alert-success",
            "message": "El proceso de registro esta en estatus: <strong>Aprobado</strong>."
        },
        "En revisión": {
            "class": "alert-warning",
            "message": "El proceso de registro esta en estatus: <strong>En revisión</strong>. Esperando aprobación de los datos"
        },
        "Rechazado": {
            "class": "alert-danger",
            "message": "El proceso de registro esta en estatus: <strong>Rechazado</strong>. Puede ver el motivo del rechazo en el siguiente enlace. <a class='link_modal' data-toggle='modal' data-target='#reject_motive'> Ver motivos</a>"
        }
    };

    if (["Aprobado", "En revisión"].includes(supplier.qp_status)) {
        $(".button-new").hide()

        $(".button-save").removeClass("is_estatus_editable")
        
        $('.finish').remove();  

        $(".form-control").prop("disabled", true);


    }

    var $alertStatus = $("#alert-status");

    var classes = $alertStatus.attr("class").split(" ");

    if (classes.length > 1) {
        $alertStatus.removeClass(classes[1]);
    }

    $alertStatus.addClass(alert_estatus[supplier.qp_status].class);


    $alertStatus.html(alert_estatus[supplier.qp_status].message);

}

function setOptionCities(cities_list) {
    const $selectElement = $("#city");

    $selectElement.find('option').not('[value="0"]').remove();

    $.each(cities_list, function (index, city) {
        const optionText = `${city.name} (${city.state_name})`;
        $selectElement.append(new Option(optionText, city.name));
    });
}
function setOptionStates(states_list) {
    const $selectElement = $("#state");

    $selectElement.find('option').not('[value="0"]').remove();

    $.each(states_list, function (index, state) {
        const optionText = `${state.name} (${state.municipality_name})`;
        $selectElement.append(new Option(optionText, state.name));
    });
}



function send_upload(method, formData, callresponse) {

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

        xhr.open('POST', method, true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
        xhr.send(formData);

    })
}
















function openNav() {
    document.getElementById("mySidenav").style.width = "250px";
    document.getElementById("overlay").style.display = "block";
}

function closeNav() {
    document.getElementById("mySidenav").style.width = "0";
    document.getElementById("overlay").style.display = "none";
}
