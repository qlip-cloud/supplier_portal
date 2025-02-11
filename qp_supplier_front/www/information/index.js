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

    $('.form-estandar').on('submit', function (event) {

        event.preventDefault(); // Evita el envío del formulario

        var formData = new FormData(this);

        supplier_id = $("#supplier_id").val();

        formData.append("supplier_id", supplier_id);

        callresponse = (response) => {

            data = response.data

            frappe.msgprint(response.msg)

            if (data.redirect_to) {
                window.location.href = data.redirect_to
            }

            if ($(this).hasClass("form-modal")) {

                $('.modal').modal('hide')

            }

            $(this).attr('method', $(this).data("method-default"));

            if (data.render) {

                render = data.render

                $(`#${render.container}`).html(render.list)
            }
            console.log(data)

            setup_button(data.supplier)

        }

        petition_send_data(formData, $(this).attr('action'), callresponse, $(this).attr('method'))

    });

    $('#form-document').on('submit', function (event) {

        event.preventDefault(); // Evita el envío del formulario

        var data = { "documents": {} };

        $('#form-document input[data-document]').each(function () {
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

        callresponse = (response) => {

            frappe.msgprint(response.msg)

            data = response.data
            console.log(data)
            setup_button(data.supplier)
        }

        petition_get_data(data, $(this).attr('action'), callresponse)

    });


    $(".open_folder").on("click", function () {
        console.log("open_folder")
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

            $dataPhone.val(contact.phone_nos[0].phone);

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
                $(`#file_full-${setting_id} a`).html(data.file_name)
                $(`#file1-${setting_id}`).val(data.file_url)
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

    const alert_estatus = {"En proceso": "alert-info", "Aprobado": "alert-success", "En revisión": "alert-warning", "Rechazado": "alert-danger" };

    if (["Aprobado", "En revisión"].includes(supplier.qp_status)) {

        $(".button-save").hide()

        var $alertStatus = $("#alert-status");

        var classes = $alertStatus.attr("class").split(" ");

        if (classes.length > 1) {
            $alertStatus.removeClass(classes[1]);
        }

        $alertStatus.addClass(alert_estatus[supplier.qp_status]);

        $(".form-control").prop("disabled", true);
        $("#qp-status").html(supplier.qp_status);
    }

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
