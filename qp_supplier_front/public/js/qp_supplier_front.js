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
    $("#accordion").on("click",".page-link", function(){

        var nav =  $(this).closest('nav');
        console.log(nav)
        action = $(nav.data("reference"));
        console.log(action)

        page = $(this).data("page")

        target = $(action).data("target")

        url = `qp_supplier_front.resources.utils.pagination.render_detail`;

            data = {
                "key": $(action).data("key"),
                "doctype": $(action).data("doctype"),
                "name": $(action).data("name"),
                page
            }

            callresponse = (response) => {
                
                if (response.data.trim() === "") {

                    return;
                }

                $(target).html(response.data);
                
            }


            petition_get_data(data, url, callresponse)
    });

    $(".filter-list").on("input", function(){

        currentPage = -1;
        accordion = $("#accordion");
        
        clearTimeout(debounceTimer);
        
        debounceTimer = setTimeout(function() {
            accordion.html("")
            loadMoreInvoices()
        }, 300);

    })
    
    $("#accordion").on("click", ".detail-row", function(){

        if ($(this).hasClass("empty-data")){

            target = $(this).data("target")

            url = `qp_supplier_front.resources.utils.pagination.render_detail`;

            data = {
                "key": $(this).data("key"),
                "doctype": $(this).data("doctype"),
                "name": $(this).data("name")
            }

            callresponse = (response) => {
                
                if (response.data.trim() === "") {

                    return;
                }
                $(this).removeClass("empty-data")

                $(target).html(response.data);
                
            }


            petition_get_data(data, url, callresponse)
        }
    })


    $(window).scroll(function () {
        if ($(window).scrollTop() + $(window).height() >= $(document).height()) {
            loadMoreInvoices();
        }
    });

    function loadMoreInvoices() {

        currentPage++;



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

function performSearch(query) {
    // Lógica para realizar la búsqueda
    console.log("Buscando: " + query);
    // Aquí puedes hacer la petición AJAX o cualquier otra lógica de búsqueda
  }


function getValidInputs() {
    var inputs = {};
    
    $('.filter-list').each(function() {
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
