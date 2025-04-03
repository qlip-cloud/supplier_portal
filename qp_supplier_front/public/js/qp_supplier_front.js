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

            $(this).css({'background-color': "#EEF0F2"});

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
        }else{
            showPopup()
        }
    });

    $(".filter-list").on("input", function () {

        currentPage = -1;
        accordion = $("#accordion");

        clearTimeout(debounceTimer);

        debounceTimer = setTimeout(function () {
            accordion.html("")
            loadMoreInvoices()
        }, 300);

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

    function loadMoreInvoices() {

        currentPage++;

        if (loading == false && no_more == false) {

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
});

function getValidInputs() {
    var inputs = {};

    $('.filter-list').each(function () {
        var $input = $(this);
        var id = $input.attr('id');
        var value = $input.val().trim();

        // Verifica si el input es válido
        if ($input.is('select') && value === '0') {
            return; // Salta este input si es un select con valor 0
        }

        if (value) { // Solo agrega si el valor no está vacío
            if ($input.hasClass("date")) { // Solo agrega si el valor no está vacío
                inputs[id] = value;
            }
            else
                inputs[id] = ["like", `${value}%`];
        }
    });

    return inputs;
}


function showPopup() {
    $('#popup-sync').fadeIn(500).delay(2000).fadeOut(500);
}

$('.sidebar-menu').on('click', function() {
    closeNav();
    $('#syncModal').modal('show');
});