var take_ovarlay = true;


$(document).ready(function () {
    $('#total').text(formatearCOP(0));
    $(".dispatch-check").prop("checked", false);
    
    $('#check-all').on('change', function() {

        const isChecked = $(this).is(':checked');

        $(`.dispatch-check`).prop('checked', isChecked);

    });

    $("#finish_lot").on("click", function () {

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
    })
    $("#finish").on("click", function () {
        url = `qp_supplier_front.resources.dispatch.purchase_order.create`;


        let dispatchs = [];

        $('.dispatch-check:checked').each(function () {
            dispatchs.push($(this).val());
        });

        // 2. Validación básica: si no hay nada, no disparamos AJAX
        if (dispatchs.length === 0) {
            frappe.msgprint("Por favor, selecciona al menos un despacho.");
            return;
        }

        supplier_id = $("#supplier_id").val();

        $("#custom-overlay").show()

        petition_get_data({ supplier_id, dispatchs }, url, finished_process)
    })

    $('#accordion').on('change', '.dispatch-check', function () {
        let $checkbox = $(this);
        let $fila = $checkbox.closest('tr');

        if ($checkbox.is(':checked')) {
            // 1. Asignamos la clase al checkbox para tu uso futuro en filtros
            $checkbox.addClass('filter-notin');

            // 2. Aplicamos estilos a la fila
            $fila.addClass('selected'); // Para el color de fondo
            $fila.find('td').css('font-style', 'italic'); // Fuente itálica a todos los td
        } else {
            // 1. Quitamos la clase al checkbox
            $checkbox.removeClass('filter-notin');

            // 2. Revertimos estilos
            $fila.removeClass('selected');
            $fila.find('td').css('font-style', 'normal'); // Volver fuente a la normalidad
        }

        // --- Lógica de la suma total ---
        let sumaTotal = 0;
        $('.dispatch-check:checked').each(function () {
            let valor = parseFloat($(this).data('value')) || 0;
            sumaTotal += valor;
        });

        $('#total').text(formatearCOP(sumaTotal));
    });

    // Función auxiliar para formato de moneda Colombia
    

})


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