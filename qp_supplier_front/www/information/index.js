function saveShowTab(tabId) {

    document.getElementById("overlay").style.display = 'block';

    var $form = $(".tab-content").filter(function () {
        return $(this).css("display") !== "none";
    }).find("form");

    control = $form.data("control")

    typeAction = $form.data("type")

    supplier_id = $("#supplier_id").val();

    if (control == 'is_estatus_editable') {


        switch (typeAction) {

            case 'estandar':

                var formData = new FormData($form[0]);

                formData.append("supplier_id", supplier_id);

                callresponse = (response) => {

                    data = response.data

                    showTab(tabId)

                }

                petition_send_data(formData, $form.attr('action'), callresponse, $form.attr('method'))

                break;

            case 'document':

                var formData = getDocuments(control == 'is_estatus_editable')

                callresponse = (response) => {

                    data = response.data

                    showTab(tabId)

                    clear_file()

                }

                petition_get_data(formData, $form.attr('action'), callresponse)
                break;

            default:
                break;
        }

    } else {
        showTab(tabId)
    }


}

function showTab(tabId) {

    //frappe.msgprint(response.msg)

    const tabs = document.querySelectorAll('.tab');

    const contents = document.querySelectorAll('.tab-content');

    const form = document.getElementById('dynamicForm');

    // Remove active class from all tabs and hide all tab contents
    tabs.forEach(tab => tab.classList.remove('active'));

    contents.forEach(content => content.style.display = 'none');

    // Add active class to the clicked tab and show the corresponding tab content
    const activeTab = document.querySelector(`[onclick="saveShowTab('${tabId}')"]`);

    const activeContent = document.getElementById(tabId);

    activeTab.classList.add('active');

    activeContent.style.display = 'block';
    $("#overlay").css("display", "none");

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

    clear_file()


    $('#supplier_name').on('input', function () {
        const value = $(this).val();
        const maxLength = 65;
        const regex = /^[a-zA-Z0-9. ]*$/;

        if (value.length > maxLength) {
            $('#error_message').text('Máximo 65 caracteres permitidos.');
            $(this).val(value.substring(0, maxLength));
        } else if (!regex.test(value)) {
            $('#error_message').text('Solo se permiten letras, números, espacios y el punto (.)');
            $(this).val(value.replace(/[^a-zA-Z0-9. ]/g, ''));
        } else {
            $('#error_message').text('');
        }
    });


    $('.modal-content-scroll').on('scroll', function () {
        var $modalContent = $(this);
        var scrollHeight = $modalContent[0].scrollHeight;
        var scrollTop = $modalContent.scrollTop();
        var innerHeight = $modalContent.innerHeight();

        if (scrollTop + innerHeight >= scrollHeight - 1) {
            $modalContent.closest('.modal-content').find('.accept-button').prop('disabled', false);
        }
    });


    conduct_modal = $("#conductCodeModal")

    autorization_modal = $("#autorizationModal")

    if (autorization_modal.data("accept") === 0 && autorization_modal.data("view") != "True") {
        $('#autorizationModal').modal('show');
    } else if (conduct_modal.data("accept") === 0 && conduct_modal.data("view") != "True") {

        $('#conductCodeModal').modal('show');
    }

    $(".accept-button").on("click", function () {

        url = "qp_supplier_front.resources.information.term.accept";

        supplier_id = $("#supplier_id").val();

        accept_type = $(this).data("accept-type");

        callresponse = (response) => {

            supplier = response.data

            if (accept_type == "qp_accept_autorization_processing") {

                $('#autorizationModal').modal('hide');

                if (!supplier.qp_accept_conduct_code) {

                    $('#conductCodeModal').modal('show');
                }
            }

            if (accept_type == "qp_accept_conduct") {

                $('#conductCodeModal').modal('hide');

                if (!supplier.qp_accept_autorization_processing) {

                    $('#autorizationModal').modal('show');
                }
            }


        }

        petition_get_data({ supplier_id, accept_type }, url, callresponse)

    })

    $("#tax_id").on("blur", function () {


        tax_id = $(this).val()

        url = "qp_supplier_front.resources.supplier.supplier.find";

        callresponse = (response) => {

            supplier = response.data
            if (supplier) {
                if (supplier.qp_asigned) {
                    frappe.msgprint("Ya este proveedor esta registrado en el sistema")
                    $("#save").hide();
                    $("#supplier_name").val()
                    $(this).val()

                } else {

                    $("#supplier_name").val(supplier.supplier_name)
                }
            } else {
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

        if (!supplier_id || submitter.hasClass('is_estatus_editable') || $(this).hasClass("form-modal")) {

            document.getElementById("overlay").style.display = 'block';

            callresponse = (response) => {

                data = response.data

                if (response.status == 200) {

                    if (data.redirect_to) {
                        window.location.href = data.redirect_to
                    }

                    if ($(this).hasClass("form-modal")) {

                        $('.modal').modal('hide')

                        if (data.render) {

                            render = data.render

                            $(`#${render.container}`).html(render.list)
                        }
                        if (data.is_bank_account) {
                            $(`#new-bank-account`).addClass("hidden disabled")

                        }

                    } else {
                        if (!$(this).hasClass("form-modal")) {

                            showTab(submitter.data("control"))
                        }
                    }

                    $(this).attr('method', $(this).data("method-default"));
                } else {
                    frappe.msgprint(response.msg)


                }

                document.getElementById("overlay").style.display = 'none';
            }
            petition_send_data(formData, $(this).attr('action'), callresponse, $(this).attr('method'))
        } else {
            showTab(submitter.data("control"))

            document.getElementById("overlay").style.display = 'none';
        }

    });

    $('#form-document').on('submit', function (event) {

        event.preventDefault(); // Evita el envío del formulario

        const submitter = $(document.activeElement);

        is_estatus_editable = submitter.hasClass('is_estatus_editable');

        const formData = getDocuments(is_estatus_editable);

        if (submitter.hasClass('is_estatus_editable') || submitter.hasClass('finish')) {

            document.getElementById("overlay").style.display = 'block';

            callresponse = (response) => {

                data = response.data

                supplier = data.supplier

                if (submitter.hasClass("finish")) {
                    // Indicar en rojo los campos incompletos en cada tab

                    $('.tab').css('color', 'black');

                    // Limpiar clase status-cancelled de todos los campos
                    $('input, select, textarea').removeClass('status-cancelled');

                    has_incompleted = false

                    // Agrupar validaciones por tab
                    var tabValidations = {};

                    $.each(supplier.qp_field_validations, function (index, validation) {

                        // Buscar tabs que contengan la clase del field_section
                        const $tabs = $(`.tab[class*="${validation.field_section}"]`);

                        $tabs.each(function () {
                            const tabClasses = $(this).attr('class');

                            if (!tabValidations[tabClasses]) {
                                tabValidations[tabClasses] = {
                                    $tab: $(this),
                                    allCompleted: true
                                };
                            }

                            // Si alguna validación está incompleta, marcar el tab como incompleto
                            if (validation.is_completed === 0) {
                                tabValidations[tabClasses].allCompleted = false;

                                // Marcar campos faltantes con status-cancelled
                                if (validation.missing_fields) {
                                    const missingFields = validation.missing_fields.split(',');
                                    missingFields.forEach(function (fieldId) {
                                        const trimmedId = fieldId.trim();
                                        if (trimmedId) {
                                            // Buscar por ID o por name
                                            const $field = $(`#${trimmedId}, [name="${trimmedId}"]`);
                                            $field.addClass('status-cancelled');
                                        }
                                    });
                                }
                            }
                        });
                    });

                    // Aplicar estilos basados en el estado acumulado
                    $.each(tabValidations, function (tabClasses, tabData) {

                        if (!tabData.allCompleted) {
                            has_incompleted = true
                            tabData.$tab.css('color', 'red');
                            tabData.$tab.find('span').css('color', 'red');
                            tabData.$tab.addClass('incomplete-tab');
                        } else {
                            tabData.$tab.css('color', '#999');
                            tabData.$tab.find('span').css('color', '#999');
                            tabData.$tab.removeClass('incomplete-tab');
                        }
                    });
                    msg_error = has_incompleted ? "<p>Hay secciones sin completar, las cuales se indican en rojo. Para continuar con el proceso de validación, debe completar todos los campos.</p>" : "";

                    msg = `<p>${response.msg}</p> ${msg_error}`;

                    if (!has_incompleted) {
                        location.reload(true);
                    }

                    frappe.msgprint(msg);


                }
                if (submitter.hasClass('is_estatus_editable')) {

                    showTab(submitter.data("control"))
                }

                clear_file()

                setup_button(supplier);
                document.getElementById("overlay").style.display = 'none';

            }

            petition_get_data(formData, $(this).attr('action'), callresponse)
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

    $("#preapproved").on("click", function () {

        frappe.confirm('¿Seguro que desea pre aprobar el registro?',
            function () {

                supplier_id = $("#supplier_id").val();

                url = "qp_supplier_front.resources.supplier.supplier.pre_approved";

                callresponse = (response) => {

                    frappe.msgprint(response.msg)

                    data = response.data

                    setup_button(data.supplier)

                    $("#preapproved_legend").html("En proceso de aprobación por finanzas")

                    if (data.is_alpla_admin) {


                        $("#preapproved").hide()
                        $("#approve").show()

                    } else {

                        $(".button-row").remove()
                    }

                }


                petition_get_data({ supplier_id }, url, callresponse)


            }, function () { })
    })

    $(".doc-delete").on("click", function () {
        setting_id = $(this).data("setting-id");
        frappe.confirm('¿Seguro que desea eliminar este registro?',
            function () {
                $(`#status-${setting_id}`).text("Eliminando archivo...");


                supplier_id = $("#supplier_id").val();

                url = "qp_supplier_front.resources.information.document.delete";

                callresponse = (response) => {

                    frappe.msgprint(response.msg)

                    data = response.data
                    statusCode = response.status
                    if (statusCode == 200) {
                        $(`#status-${setting_id}`).text("Archivo no cargado");


                        $(`.upload-${setting_id}`).show()
                        $(`.empty-${setting_id}`).hide()
                    }
                    else {
                        $(`#status-${setting_id}`).text("Hubo un error eliminando el archivo");

                    }
                }


                petition_get_data({ supplier_id, setting_id }, url, callresponse)


            }, function () { })
    })

    $("#contact_list").on("click", ".contact-delete", function () {
        contact_id = $(this).data("contact-id");
        frappe.confirm('¿Seguro que desea eliminar este registro?',
            function () {
                supplier_id = $("#supplier_id").val();
                url = "qp_supplier_front.resources.information.contact.delete";
                callresponse = (response) => {
                    data = response.data
                    statusCode = response.status
                    console.log(response)
                    if (statusCode == 200) {
                        frappe.msgprint(response.msg)
                        render = data.render
                        $(`#${render.container}`).html(render.list)
                    }
                    else {
                        msg = response.msg || "Hubo un error eliminando el contacto."
                        frappe.msgprint(msg);
                    }
                }
                petition_get_data({ supplier_id, contact_id }, url, callresponse)
            }, function () { })
    })

    $('#shareholder_list').on('click', '.shareholder-delete', function () {
        shareholder_id = $(this).data("shareholder-id");
        frappe.confirm('¿Seguro que desea eliminar este registro?',
            function () {
                supplier_id = $("#supplier_id").val();
                url = "qp_supplier_front.resources.information.shareholder.delete";
                callresponse = (response) => {
                    data = response.data
                    statusCode = response.status
                    if (statusCode == 200) {
                        frappe.msgprint(response.msg)
                        render = data.render
                        $(`#${render.container}`).html(render.list)
                    }
                    else {
                        $(`#status-${shareholder_id}`).text("Hubo un error eliminando el accionista");
                    }
                }
                petition_get_data({ supplier_id, shareholder_id }, url, callresponse)
            }, function () { })
    })



    $("#bank_account_list").on("click", ".bank-account-delete", function () {

        bank_account_id = $(this).data("bank-acccount-id");

        frappe.confirm('¿Seguro que desea eliminar este registro?',
            function () {


                supplier_id = $("#supplier_id").val();


                url = "qp_supplier_front.resources.information.bank_account.delete";

                callresponse = (response) => {

                    data = response.data

                    statusCode = response.status

                    if (statusCode == 200) {

                        frappe.msgprint(response.msg)

                        render = data.render
                        $(`#${render.container}`).html(render.list)

                        if (data.bank_accounts.length === 0) {
                            $(`#new-bank-account`).removeClass("hidden disabled")
                        }
                    }
                    else {
                        $(`#status-${setting_id}`).text("Hubo un error eliminando la cuenta bancaria");

                    }
                }


                petition_get_data({ supplier_id, bank_account_id }, url, callresponse)


            }, function () { })
    })

    $('#qp_resolution_self_retaining').closest('.col-lg-4')[
        $('#qp_self_retaining').val() === 'SI' ? 'show' : 'hide'
    ]();

    $('#qp_resolution').closest('.col-lg-4')[
        $('#qp_major_contributor').val() === 'SI' ? 'show' : 'hide'
    ]();

    $('#qp_quality_cert_detail').closest('.col-6')[
        $('#qp_has_quality_cert').val() === 'SI' ? 'show' : 'hide'
    ]();

    $('#qp_self_retaining').on('change', function () {
        if ($(this).val() === 'SI') {
            $('#qp_resolution_self_retaining').closest('.col-lg-4').show();
        } else {
            $('#qp_resolution_self_retaining').closest('.col-lg-4').hide();
        }
    });

    $('#qp_major_contributor').on('change', function () {
        if ($(this).val() === 'SI') {
            $('#qp_resolution').closest('.col-lg-4').show();
        } else {
            $('#qp_resolution').closest('.col-lg-4').hide();
        }
    });

    $('#qp_has_quality_cert').on('change', function () {
        if ($(this).val() === 'SI') {
            $('#qp_quality_cert_detail').closest('.col-6').show();
        }
        else {
            $('#qp_quality_cert_detail').closest('.col-6').hide();
        }
    });


    $('#qp_reject_observation').on('input', function () {
        if ($(this).val().trim() !== '') {
            $('#reject').prop('disabled', false);
        } else {
            $('#reject').prop('disabled', true);
        }
    });

    $('[name="id_type_name"]').on('change', function () {
        if ($(this).val() === 'NIT') {
            $('#tax_id').attr('maxlength', '9');
        } else {
            $('#tax_id').attr('maxlength', '140');
        }
    })
    $('#tax_id').on('keypress', function (e) {
        const char = String.fromCharCode(e.which);
        if ($('[name="id_type_name"]').val() === 'NIT') {
            if (!/^\d$/.test(char)) {
                e.preventDefault();
            }
        }
    });
    $('#tax_id').on('keypress', function (e) {
        const char = String.fromCharCode(e.which);
        if ($('#tax_id').val().length === 9 && $('[name="id_type_name"]').val() === 'NIT') {
            e.preventDefault();
        }
    });

    $('#tax_id').on('input', function () {
        this.value = this.value.replace(/[^a-zA-Z0-9]/g, '');
    });
    $('#phone_number').on('input', function () {
        let cursor = this.selectionStart;
        let originalLen = this.value.length;

        let val = this.value.replace(/\D/g, '');
        if (val.length > 10) {
            val = val.substring(0, 10);
        }

        let formatted = '';
        if (val.length > 0) {
            formatted += '(' + val.substring(0, 3);
            if (val.length > 3) {
                formatted += ')' + val.substring(3);
            }
        }

        this.value = formatted;

        let newLen = formatted.length;
        let diff = newLen - originalLen;
        if (cursor < originalLen) {
            this.setSelectionRange(cursor + diff, cursor + diff);
        }
    }).trigger('input');

    $('#country_code').on('keypress', function (e) {
        const char = String.fromCharCode(e.which);
        if (!/^\d$/.test(char)) {
            e.preventDefault();
        }
    });

    $('#country_code').on('input', function () {
        this.value = this.value.replace(/\D/g, '');
    });

    $('#phone').on('keypress', function (e) {
        const char = String.fromCharCode(e.which);
        if (!/^\d$/.test(char)) {
            e.preventDefault();
        }
    });

    $('#phone').on('input', function () {
        this.value = this.value.replace(/\D/g, '');
    });

    $("#reject").on("click", function () {

        supplier_id = $("#supplier_id").val();

        qp_reject_observation = $("#qp_reject_observation").val();

        url = "qp_supplier_front.resources.supplier.supplier.reject";

        callresponse = (response) => {

            frappe.msgprint(response.msg)

            $('.modal').modal('hide')

            data = response.data

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

    $("#new-address").on("click", function () {
        $("#form-address")[0].reset();
        $("#form-address").find("input[type='text'], select").val("").trigger('change');
        $("#form-address").attr('method', 'POST');
    });
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
            const $dataCountryCode = $("#country_code");
            const $contactType = $("#qp_contact_type");

            $doctype_id.val(contact_id);

            $dataFirstName.val(contact.first_name);

            $dataEmailId.val(contact?.email_ids?.[0]?.email_id || contact?.user);

            let phone = contact.phone_nos.length ? contact.phone_nos[0].phone : "";
            let country_code = "";
            let phone_number = "";

            if (phone.includes(" ")) {
                const parts = phone.split(" ");
                country_code = parts[0];
                phone_number = parts.slice(1).join(" ");
            } else {
                phone_number = phone;
            }

            $dataCountryCode.val(country_code);
            $dataPhone.val(phone_number);
            $contactType.val(contact.qp_contact_type);

            $("#form-contact").attr('method', 'PUT');
            $('#contact_modal').modal('show')
        }

        petition_get_data({ contact_id }, url, callresponse)
    })


    $("#new-contact").on("click", function () {
        $("#form-contact")[0].reset();
        $("#form-contact").find("input[type='text'], select").val("").trigger('change');
        $("#form-contact").attr('method', 'POST');
    });

    $("#bank_account_list").on("click", ".bank_account-id", function () {

        bank_account_id = $(this).data("id");

        url = "qp_supplier_front.resources.information.bank_account.search_bank_account";

        callresponse = (response) => {
            const data = response.data
            const bank_account = data.bank_account
            const bank = data.bank


            const $doctype_id = $("#form-bank-account [name='doctype_id']");

            const $selectBank = $("#bank");
            const $selectAccountType = $("#account_type");
            const $dataBankAccount_no = $("#bank_account_no");
            const $swiftNumber = $("#swift_number");
            const $abaNumber = $("#qp_aba_number");
            const $ibanNumber = $("#iban");
            const $qp_routing_code = $("#qp_routing_code");

            $doctype_id.val(bank_account_id);

            $selectBank.val(bank_account.bank);

            $selectAccountType.val(bank_account.account_type);

            $dataBankAccount_no.val(bank_account.bank_account_no);

            $swiftNumber.val(bank.qp_swift_number || "");
            $abaNumber.val(bank.qp_aba_number || "");
            $ibanNumber.val(bank_account.qp_iban_number || "");
            $qp_routing_code.val(bank_account.qp_routing_code || "");

            const is_synced = bank_account.qp_from_sync === 1;
            const is_page_editable = !$("#qp_public_resource_management").prop("disabled");

            if (is_synced) {
                $selectBank.prop("disabled", true);
                $selectAccountType.prop("disabled", true);
                $dataBankAccount_no.prop("disabled", true);
                $swiftNumber.prop("disabled", true);
                $abaNumber.prop("disabled", true);
                $ibanNumber.prop("disabled", true);
                $qp_routing_code.prop("disabled", true);
                $("#form-bank-account #save").addClass("hidden disabled").prop("disabled", true);
            } else {
                $selectBank.prop("disabled", !is_page_editable);
                $selectAccountType.prop("disabled", !is_page_editable);
                $dataBankAccount_no.prop("disabled", !is_page_editable);
                $swiftNumber.prop("disabled", !is_page_editable);
                $abaNumber.prop("disabled", !is_page_editable);
                $ibanNumber.prop("disabled", !is_page_editable);
                $qp_routing_code.prop("disabled", !is_page_editable);
                if (is_page_editable) {
                    $("#form-bank-account #save").removeClass("hidden disabled").prop("disabled", false);
                } else {
                    $("#form-bank-account #save").addClass("hidden disabled").prop("disabled", true);
                }
            }

            $("#form-bank-account").attr('method', 'PUT');
            $('#bank_account_modal').modal('show')
        }

        petition_get_data({ bank_account_id }, url, callresponse)
    })

    $("#new-bank-account").on("click", function () {
        $("#form-bank-account")[0].reset();
        $("#form-bank-account").find("input[type='text'], select").val("").trigger('change');
        $("#form-bank-account").attr('method', 'POST');

        const is_page_editable = !$("#qp_public_resource_management").prop("disabled");
        const $selectBank = $("#bank");
        const $selectAccountType = $("#account_type");
        const $dataBankAccount_no = $("#bank_account_no");
        const $swiftNumber = $("#swift_number");
        const $abaNumber = $("#qp_aba_number");
        const $ibanNumber = $("#iban");
        const $qp_routing_code = $("#qp_routing_code");

        $selectBank.prop("disabled", !is_page_editable);
        $selectAccountType.prop("disabled", !is_page_editable);
        $dataBankAccount_no.prop("disabled", !is_page_editable);
        $swiftNumber.prop("disabled", !is_page_editable);
        $abaNumber.prop("disabled", !is_page_editable);
        $ibanNumber.prop("disabled", !is_page_editable);
        $qp_routing_code.prop("disabled", !is_page_editable);
        if (is_page_editable) {
            $("#form-bank-account #save").removeClass("hidden disabled").prop("disabled", false);
        } else {
            $("#form-bank-account #save").addClass("hidden disabled").prop("disabled", true);
        }
    });
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


            $doctype_id.val(shareholder_id);

            $dataFulname.val(shareholder.fullname);
            $dataNationality.val(shareholder.nationality);
            $selectHaveResidentAnotherCountry.val(shareholder.have_resident_another_country);
            $selectHaveAmericanVisa.val(shareholder.have_american_visa);
            $selectIdType.val(shareholder.id_type);
            $dataTaxId.val(shareholder.tax_id);
            $dataMarketShare.val(shareholder.market_share);

            $("#form-shareholder").attr('method', 'PUT');
            $('#shareholder_modal').modal('show')
        }

        petition_get_data({ shareholder_id }, url, callresponse)
    })
    $("#new-shareholder").on("click", function () {
        $("#form-shareholder")[0].reset();
        $("#form-shareholder").find("input[type='text'], select").val("").trigger('change');
        $("#form-shareholder").attr('method', 'POST');
    });

    $("#request-edit-btn").on("click", function () {
        const supplier_id = $("#supplier_id").val();

        const url = "qp_supplier_front.resources.information.basic.request_edit";

        const callresponse = (response) => {
            frappe.msgprint("Solicitud de edición enviada correctamente.");

            $("#request-edit-btn").replaceWith(`
                <span class="badge bg-secondary text-white ms-auto">Solicitud de edición enviada</span>
            `);
        };

        petition_get_data({ supplier_id }, url, callresponse);
    });

    $("#approve-edit-btn").on("click", function () {
        const supplier_id = $("#supplier_id").val();

        const url = "qp_supplier_front.resources.information.basic.approve_edit";

        const callresponse = (response) => {
            frappe.msgprint("Solicitud de edición aprobada correctamente.");
            setTimeout(() => {
                location.reload();
            }, 1000);
        };

        petition_get_data({ supplier_id }, url, callresponse);
    });

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

        $(`#status-${setting_id}`).text("Cargando archivo...");

        callback = (status, data) => {

            if (status == 200) {

                $(`#file_loading-${setting_id}`).hide()
                $(`#file_full-${setting_id} a`).attr('href', data.file_url);
                $(`#file_full-${setting_id} a`).html("Ver archivo")
                $(`#link-${setting_id}`).val(data.file_url)
                $(`#file_id_${setting_id}`).val(data.name)
                $(`#link-${setting_id}`).attr("data-updated", "1")
                $(`#file_full-${setting_id}`).show()
                $(`#file_full-${setting_id}`).show()

                $(`#status-${setting_id}`).text("Archivo cargado");

                $(`#link-${setting_id}`).val(data.file_url);
                $(`#link-${setting_id}`).attr("data-updated", "1");
                $(`.upload-${setting_id}`).hide()

                $view_link = $(`#view-${setting_id}`)
                $view_link.prop("href", data.file_url)
                $(`.empty-${setting_id}`).show()
                //data.file_url
            } else {
                $(`#file_empty-${setting_id}`).show()
                $(`#file_loading-${setting_id}`).hide()
                $(`#status-${setting_id}`).text("Error al cargar el archivo, intente nuevamente");
            }

        }
        method = "/api/method/upload_file"

        send_upload(method, formData, callback)

    })
});

function getDocuments(is_estatus_editable) {

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

    data["is_estatus_editable"] = is_estatus_editable;

    qp_has_quality_cert = $("#qp_has_quality_cert").val();

    data["qp_has_quality_cert"] = qp_has_quality_cert;

    if (qp_has_quality_cert == "NO" || qp_has_quality_cert == "") {
        data["qp_quality_cert_detail"] = "";
    } else {
        data["qp_quality_cert_detail"] = $("#qp_quality_cert_detail").val();
    }


    return data
}
function clear_file() {
    $('.file-link').each(function () {
        let $newInput = $(this).clone();
        $newInput.val('');
        $(this).replaceWith($newInput);
    });
}
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

        const result = classes.find(str => str.startsWith("alert-"));

        $alertStatus.removeClass(result);
    }

    $alertStatus.addClass(alert_estatus[supplier.qp_status].class);


    $alertStatus.find("div:first").html(alert_estatus[supplier.qp_status].message);

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



