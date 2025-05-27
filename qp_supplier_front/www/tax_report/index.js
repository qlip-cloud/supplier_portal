$(document).ready(function() {

    var select = $('#year');

    var initFiscalYear = parseInt(select.data('init_fiscal_year'));

    var currentYear = new Date().getFullYear();

    for (var year = initFiscalYear; year <= currentYear; year++) {
        select.append('<option value="' + year + '">' + year + '</option>');
        console.log()
    }

    $("#save").on("click", function () {

        supplier_id = $("#supplier_id").val();
        report_type = $("#report_type").val();
        fiscal_year = $("#year").val();
        bimester = $("#bimester").val();

        var url = "api/method/qp_supplier_front.resources.tax_report.download.report";

        var noCacheUrl = url + '?nocache=' + new Date().getTime() +
                         '&supplier_id=' + encodeURIComponent(supplier_id) +
                         '&report_type=' + encodeURIComponent(report_type) +
                         '&fiscal_year=' + encodeURIComponent(fiscal_year) +
                         '&bimester=' + encodeURIComponent(bimester);

        window.open(noCacheUrl, '_blank');

    })

});