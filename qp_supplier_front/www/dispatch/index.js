var take_ovarlay = true;


$(document).ready(function () {

    $(".filter-list").on("input", function () {
        
        if ($("#errorsButton").length > 0){

            filters = getValidInputs();

            supplier_id = $("#supplier_id").val();

            url = `qp_supplier_front.resources.dispatch.dispatch.search_error_filter`;

            callresponse = (response) => {

                status_code = response.status

                data = response.data

                template = data.template

                total_errors = data.total_errors

                $("#total_errors").text(total_errors)

                $("#errorsModal .modal-body").html(template)

            }

            petition_get_data({ supplier_id, filters }, url, callresponse)

        }

    })
    $('#total').text(formatearCOP(0));
    $(".dispatch-check").prop("checked", false);

    $('#check-all').on('change', function () {

        const isChecked = $(this).is(':checked');

        $(`.dispatch-check`).prop('checked', isChecked);

    });

    $("#finish_lot").on("click", function () {
        if (validateFilterList()) {
            url = `qp_supplier_front.resources.dispatch.dispatch.search_detail_filter_lot`;


            let filters = getValidInputs();

            take_ovarlay = false

            supplier_id = $("#supplier_id").val();

            callresponse = (response) => {

                status_code = response.status

                loading = false;

                data = response.data

                frappe.confirm(`Se procesaran <strong> ${data.count} </strong> despachos por un total de <strong> ${formatearCOP(data.total)} </strong> <br> ¿Seguro que desea continuar?`,
                    function () {

                        supplier_id = $("#supplier_id").val();

                        url = `qp_supplier_front.resources.dispatch.purchase_order.create_by_filter`;

                        $("#custom-overlay").show()

                        petition_get_data({ supplier_id, filters }, url, finished_process)

                    }, function () {
                        $('#custom-overlay').hide();

                    })

            }
            $("#custom-overlay").show()

            petition_get_data({ supplier_id, filters }, url, callresponse)
        } else {
            frappe.msgprint("Esta acción requiere que haya indicado al menos un filtro.")
        }
    })
    $("#finish").on("click", function () {




        let dispatchs = [];

        $('.dispatch-check:checked').each(function () {
            dispatchs.push($(this).val());
        });

        // 2. Validación básica: si no hay nada, no disparamos AJAX
        if (dispatchs.length === 0) {
            frappe.msgprint("Por favor, selecciona al menos un despacho.");
            return;
        }

        frappe.confirm(`Se procesaran <strong> ${dispatchs.length} </strong> despachos por un total de <strong> ${formatearCOP(getTotal())} </strong> <br> ¿Seguro que desea continuar?`,
            function () {

                url = `qp_supplier_front.resources.dispatch.purchase_order.create`;
                supplier_id = $("#supplier_id").val();

                $("#custom-overlay").show()

                petition_get_data({ supplier_id, dispatchs }, url, finished_process)
            }, function () {
                $('#custom-overlay').hide();

            })
    })

    $('#accordion').on('change', '.dispatch-check', function () {

        let $checkbox = $(this);
        let $fila = $checkbox.closest('tr');

        if ($checkbox.is(':checked')) {
            $checkbox.addClass('filter-notin');

            $fila.addClass('selected');
            $fila.find('td').css('font-style', 'italic');
        } else {
            $checkbox.removeClass('filter-notin');

            $fila.removeClass('selected');
            $fila.find('td').css('font-style', 'normal');
        }

        
        $('#total').text(formatearCOP(getTotal()));
    });
})

function getTotal(){

    let total = 0;

        $('.dispatch-check:checked').each(function () {
            let value = parseFloat($(this).data('value')) || 0;
            total += value;
        });

    return total;

}

function finished_process(response) {

    status_code = response.status

    loading = false;

    take_ovarlay = true

    data = response.data

    $('#total').text(formatearCOP(0));

    $("#accordion").html(data)

    $('#custom-overlay').hide();

    $(".filter-list").val("")

    $(".filter-list.filter-check").val("0")

    frappe.msgprint("Despacho creado exitosamente", "Exito")
}

function formatearCOP(valor) {
    return new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        minimumFractionDigits: 0
    }).format(valor);
}

function validateFilterList() {
    const selectors = [
        'input[type="text"].filter-list',
        'input[type="date"].filter-list',
        'select.filter-list'
    ].join(', ');

    const elements = document.querySelectorAll(selectors);

    const hasValue = Array.from(elements).some(el => {
        return el.value.trim() !== "";
    });

    return hasValue;
};