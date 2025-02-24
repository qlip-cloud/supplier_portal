function openNav() {
    document.getElementById("mySidenav").style.width = "250px";
    document.getElementById("overlay").style.display = "block";
}

function closeNav() {
    document.getElementById("mySidenav").style.width = "0";
    document.getElementById("overlay").style.display = "none";
}


$(document).ready(function () {
    $('.number').on('input', function () {
        let value = $(this).val().replace(/\D/g, ''); // Eliminar cualquier carácter que no sea un número
        if (value.length > 0) {
            value = (parseInt(value) / 100).toFixed(2); // Convertir a decimal con dos decimales
        }
        $(this).val(value);
    });

    let currentPage = 1;
    let loading = false;
    $(window).scroll(function () {
        if ($(window).scrollTop() + $(window).height() >= $(document).height()) {
            loadMoreInvoices();
        }
    });

    function loadMoreInvoices() {

        currentPage++;

        accordion = $("#accordion");

        url = `qp_supplier_front.resources.utils.pagination.render_pagination`;

        data = {
            'page': currentPage,
            "key": accordion.data("key"),
        }

        callresponse = (response) => {
            if (response.data.trim() === "") {
                // No more data to load
                $(window).off('scroll');
                return;
            }
            accordion.append(response.data);
            loading = false;
        }

        petition_get_data(data, url, callresponse)

    }
});


