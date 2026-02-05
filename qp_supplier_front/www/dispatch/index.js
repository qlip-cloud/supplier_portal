$(document).ready(function () {
    $('#total').text(formatearCOP(0));
    $(".dispatch-check").prop("checked", false);
    
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

        callresponse = (response) => {

            status_code = response.status

            loading = false;

            data = response.data
            
            $('#total').text(formatearCOP(0));

            $("#accordion").html(data)

            $('#custom-overlay').hide();
            frappe.msgprint("Despacho creado exitosamente", "Exito")

        }
        $("#custom-overlay").show()

        petition_get_data({ supplier_id, dispatchs }, url, callresponse)
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
    function formatearCOP(valor) {
        return new Intl.NumberFormat('es-CO', {
            style: 'currency',
            currency: 'COP',
            minimumFractionDigits: 0
        }).format(valor);
    }

})
