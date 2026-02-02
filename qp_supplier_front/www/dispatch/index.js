$(document).ready(function() {
    $('#total').text(formatearCOP(0));
    $("#finish").on("click", function(){

        url = `qp_supplier_front.resources.dispatch.purchase_order.create`;

        
        let dispatchs = [];
        
        $('.dispatch-check:checked').each(function() {
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

        }
                
        petition_get_data({supplier_id, dispatchs}, url, callresponse)
    })

    $('#accordion').on('change', '.dispatch-check',function() {
        let sumaTotal = 0;

        // Recorrer solo los que están marcados
        $('.dispatch-check:checked').each(function() {
            // Convertir a número el data-value (asegúrate que venga sin símbolos de moneda)
            let valor = parseFloat($(this).data('value')) || 0;
            sumaTotal += valor;
        });

        // Formatear a moneda COP y asignar al elemento #total
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
