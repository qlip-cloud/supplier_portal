$(document).ready(function () {

    $("#assign-document").on("click", function () {
        var selected = $('tbody input[type="checkbox"]:checked');
        if (selected.length === 0) {
            frappe.msgprint("Seleccione al menos una factura");
            return;
        }

        var doc_names = [];
        selected.each(function () {
            doc_names.push($(this).val());
        });

        var $tbody = $("#assign-table-body");
        $tbody.empty();

        var $select = $("#assign-user-select");
        $select.prop("disabled", true).html('<option value="">Cargando usuarios...</option>');

        petition_get_data({}, "qp_supplier_front.resources.documenteme.assign.get_users", function (response) {
            $select.prop("disabled", false).html('<option value="">Seleccione un usuario</option>');
            if (response.data && response.data.length > 0) {
                response.data.forEach(function (u) {
                    var fullName = u.first_name + " " + (u.last_name || "");
                    $select.append('<option value="' + u.name + '">' + fullName.trim() + '</option>');
                });
            }
        });

        petition_get_data({
            doc_names: JSON.stringify(doc_names)
        }, "qp_supplier_front.resources.documenteme.assign.get_document_data", function (response) {
            if (response.data && response.data.length > 0) {
                response.data.forEach(function (doc) {
                    $tbody.append(
                        "<tr><td>" + (doc.nvfac_nume || "") + "</td><td>" + (doc.nvfac_orde || "") + "</td><td>" + (doc.nvfac_rece || "") + "</td></tr>"
                    );
                });
            }
        });

        $("#assign_invoice_modal").modal("show");
    });

    $("#approve-document").on("click", function () {
        frappe.msgprint("Funcionalidad aun no disponible");
    });

    $("#reject-document").on("click", function () {
        var selected = $('tbody input[type="checkbox"]:checked');
        if (selected.length === 0) {
            frappe.msgprint("Seleccione al menos una factura");
            return;
        }
        $("#reject_invoice_motive").modal("show");
    });

    $("#motive_text").on("input", function () {
        if ($(this).val().trim() !== "") {
            $("#confirm-reject").prop("disabled", false);
        } else {
            $("#confirm-reject").prop("disabled", true);
        }
    });

    $(document).on("click", ".btn-control-alert", function () {
        frappe.msgprint("Funcionalidad de alerta por implementar");
    });

    $(document).on("click", ".btn-control-assign", function () {
        frappe.msgprint("Funcionalidad de asignación por implementar");
    });

    $(document).on("click", ".btn-control-download", function () {
        var name = $(this).data("name");
        var nvfacNume = $(this).data("nvfac-nume");
        var url = "/api/method/qp_supplier_front.resources.documenteme.download.files";
        var noCacheUrl = url + "?nocache=" + new Date().getTime() +
                         "&doc_name=" + encodeURIComponent(name) +
                         "&invoice_number=" + encodeURIComponent(nvfacNume);
        window.open(noCacheUrl, "_blank");
    });

    $("#confirm-reject").on("click", function () {
        var doc_names = [];
        $('tbody input[type="checkbox"]:checked').each(function () {
            doc_names.push($(this).val());
        });
        var motive = $("#motive_text").val().trim();
        var is_invoice_error = $("#is_invoice_error").is(":checked");

        $("#motive_text").val("");
        $("#is_invoice_error").prop("checked", false);
        $("#confirm-reject").prop("disabled", true);
        $("#reject_invoice_motive").modal("hide");

        var overlayEl = document.getElementById("overlay");
        var savedOnClick = overlayEl.onclick;
        overlayEl.onclick = null;
        overlayEl.style.display = "block";

        var url = "qp_supplier_front.resources.documenteme.reject.reject";

        callresponse = (response) => {
            overlayEl.onclick = savedOnClick;
            overlayEl.style.display = "none";
            frappe.msgprint(response.msg);
            if (response.status === 200) {
                $('tbody input[type="checkbox"]:checked').each(function () {
                    $(this).closest("tr").remove();
                });
                loadMoreInvoices(true);
            }
        };

        petition_get_data({
            doc_names: JSON.stringify(doc_names),
            motive: motive,
            is_invoice_error: JSON.stringify(is_invoice_error)
        }, url, callresponse);
    });

    $("#confirm-assign").on("click", function () {
        var user = $("#assign-user-select").val();
        if (!user) {
            frappe.msgprint("Seleccione un usuario para asignar");
            return;
        }

        var doc_names = [];
        $('tbody input[type="checkbox"]:checked').each(function () {
            doc_names.push($(this).val());
        });

        var userName = $("#assign-user-select option:selected").text();

        $("#confirm-assign").prop("disabled", true);
        $("#assign_invoice_modal").modal("hide");

        var overlayEl = document.getElementById("overlay");
        var savedOnClick = overlayEl.onclick;
        overlayEl.onclick = null;
        overlayEl.style.display = "block";

        var url = "qp_supplier_front.resources.documenteme.assign.assign";

        callresponse = (response) => {
            overlayEl.onclick = savedOnClick;
            overlayEl.style.display = "none";
            $("#confirm-assign").prop("disabled", false);
            frappe.msgprint(response.msg);
            if (response.status === 200) {
                $('tbody input[type="checkbox"]:checked').each(function () {
                    var $btn = $(this).closest("tr").find(".btn-control-assign");
                    $btn.css("color", "#007bff");
                    $btn.attr("title", "Asignado a:\n- " + userName);
                });
                $('tbody input[type="checkbox"]:checked').prop("checked", false);
            }
        };

        petition_get_data({
            doc_names: JSON.stringify(doc_names),
            user: user
        }, url, callresponse);
    });

});