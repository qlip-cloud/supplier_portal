function openNav() {
    document.getElementById("mySidenav").style.width = "250px";
    document.getElementById("overlay").style.display = "block";
}

function closeNav() {
    document.getElementById("mySidenav").style.width = "0";
    document.getElementById("overlay").style.display = "none";
}


$(document).ready(function () {
    let currentPage = 0;
    let loading = false;
    let no_more = false;
    var debounceTimer;
    const today = new Date().toISOString().split("T")[0];

    if ($("#page-rfq").length) {
        $("#page-rfq .sidebar-column.col-sm-2, #page-rfq .page-breadcrumbs").remove();
    }

    $('.number').on('input', function () {
        let value = $(this).val().replace(/\D/g, ''); // Eliminar cualquier carácter que no sea un número
        if (value.length > 0) {
            value = (parseInt(value) / 100).toFixed(2); // Convertir a decimal con dos decimales
        }
        $(this).val(value);
    });

    $("#accordion").on("click", ".page-link", function () {

        if (loading == false) {
            let activeElement = $('.page-item.active');

            activeElement.removeClass('active');

            $(this).css({ 'background-color': "#EEF0F2" });

            loading = true

            var nav = $(this).closest('nav');

            action = $(nav.data("reference"));

            page = $(this).data("page")

            target = $(action).data("target")

            url = `qp_supplier_front.resources.utils.pagination.render_detail`;

            data = {
                "key": $(action).data("key"),
                "parent_doctype": $(action).data("parent-doctype"),
                "doctype": $(action).data("doctype"),
                "name": $(action).data("name"),
                page
            }

            callresponse = (response) => {

                loading = false

                if (response.data.trim() === "") {

                    return;
                }

                $(target).html(response.data);

            }


            petition_get_data(data, url, callresponse)
        } else {
            showPopup()
        }
    });



    // Establecer la fecha máxima inicial
    $("#start_date, #end_date").attr("max", today);

    // Cuando cambia la fecha de inicio
    $("#start_date").on("change", function () {
        const startDate = $(this).val();
        $("#end_date").attr("min", startDate);
    });

    // Cuando cambia la fecha de fin
    $("#end_date").on("change", function () {
        const endDate = $(this).val();
        $("#start_date").attr("max", endDate);
    });

    $(".filter-list").on("input", function () {

        filter_init()

    })

    $("#refresh_filter_list").on("click", function () {
        $(".filter-list").val("")
        filter_init()
    })

    $("#accordion").on("click", ".detail-row", function () {

        if (loading == false) {


            if ($(this).hasClass("empty-data")) {

                loading = true;

                target = $(this).data("target");

                $(target).collapse('toggle');

                url = `qp_supplier_front.resources.utils.pagination.render_detail`;

                data = {
                    "key": $(this).data("key"),
                    "parent_doctype": $(this).data("parent-doctype"),
                    "doctype": $(this).data("doctype"),
                    "name": $(this).data("name")
                }

                callresponse = (response) => {
                    loading = false;

                    if (response.data.trim() === "") {
                        return;
                    }

                    $(this).removeClass("empty-data")


                    $(target).html(response.data);


                }

                petition_get_data(data, url, callresponse)
            }
        } else {
            showPopup()
        }
    })


    $(window).scroll(function () {
        if ($(window).scrollTop() + $(window).height() >= $(document).height()) {
            loadMoreInvoices();
        }
    });

    function loadMoreInvoices(is_filter = false) {

        currentPage++;

        if ($("#no-load").length === 0) {



            if (is_filter || (loading == false && no_more == false)) {

                $("#no-more").hide()

                loading = true;

                $("#loading").show()

                accordion = $("#accordion");

                supplier_id = $("#supplier_id").val();

                url = `qp_supplier_front.resources.utils.pagination.render_pagination`;
                filters = getValidInputs();

                data = {
                    'page': currentPage,
                    "key": accordion.data("key"),
                    "doctype": accordion.data("doctype"),
                    "doctype_detail": accordion.data("doctype_detail"),
                    "order_by": accordion.data("order_by"),
                    "date_key": accordion.data("date_key"),
                    supplier_id,
                    filters
                }

                callresponse = (response) => {
                    loading = false;

                    if (response.data.trim() === "") {
                        // No more data to load
                        $(window).off('scroll');
                        no_more = true;
                        $("#no-more").show()
                        $("#loading").hide()

                        return;
                    }

                    accordion.append(response.data);

                    $("#loading").hide()

                }

                petition_get_data(data, url, callresponse)

            } else {
                showPopup()
            }

        }
    }
    function filter_init() {
        currentPage = -1;
        accordion = $("#accordion");

        clearTimeout(debounceTimer);

        debounceTimer = setTimeout(function () {
            accordion.html("")
            loadMoreInvoices(true)
        }, 300);
    }
});



function getValidInputs() {
    var inputs = {};

    let $start_date = $("#start_date")
    let $end_date = $("#end_date")
    date_key = $start_date.data("date_key")
    console.log($start_date)
    if ($start_date.val()){
        if ($start_date.val().trim() && $end_date.val().trim()) {
            inputs[date_key] = ["between", [$start_date.val(), $end_date.val()]]
        } else {

            if ($start_date.val().trim()) {
                inputs[date_key] = [">=", $start_date.val()]
            }

            if ($end_date.val().trim()) {

                inputs[date_key] = ["<=", $end_date.val()]
            }
        }
    }

    $('.filter-list').each(function () {
        var $input = $(this);
        console.log($input)
        var id = $input.attr('id');
        var value = $input.val() ? $input.val().trim() : null

        // Verifica si el input es válido
        if ($input.is('select') && value === '0') {
            return; // Salta este input si es un select con valor 0
        }

        if (value) {
            if ($input.hasClass("date")) { // Solo agrega si el valor no está vacío
                return;
            }
            else // Solo agrega si el valor no está vacío
                inputs[id] = ["like", `${value}%`];
        }
    });

    return inputs;
}


function showPopup() {
    $('#popup-sync').fadeIn(500).delay(2000).fadeOut(500);
}

$('.sidebar-menu').on('click', function () {
    closeNav();
    $('#syncModal').modal('show');
});