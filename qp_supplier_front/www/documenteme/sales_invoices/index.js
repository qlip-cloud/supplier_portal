$(document).ready(function () {

    var assignTargetDoc = null;

    $('tbody input[type="checkbox"]').prop("checked", false);

    $("#assign-document").on("click", function () {
        assignTargetDoc = null;
        $("#assign_invoice_modal_label").text("Asignar Facturas");

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
        var selected = $('tbody input[type="checkbox"]:checked');
        if (selected.length === 0) {
            frappe.msgprint("Seleccione al menos una factura");
            return;
        }

        var overlayEl = document.getElementById("overlay");
        var savedOnClick = overlayEl.onclick;

        var doc_names = [];
        selected.each(function () {
            doc_names.push($(this).val());
        });

        var doApprove = function (force) {
            overlayEl.onclick = null;
            overlayEl.style.display = "block";

            var url = "qp_supplier_front.resources.documenteme.approve.approve";

            callresponse = (response) => {
                overlayEl.onclick = savedOnClick;
                overlayEl.style.display = "none";
                frappe.msgprint(response.msg);
                if (response.status === 200) {
                    var approvedNames = (response.data && response.data.approved || []).map(function (item) {
                        return item.name;
                    });
                    $('tbody input[type="checkbox"]:checked').each(function () {
                        var $row = $(this).closest("tr");
                        if (approvedNames.indexOf($(this).val()) !== -1) {
                            $row.find(".status-badge")
                                .removeClass("status-open status-ready status-cancelled status-default")
                                .addClass("status-paid")
                                .text("Creada en BC");
                        }
                        $(this).prop("checked", false);
                    });
                }
                var serverErrors = (response.data && response.data.errors) || [];
                if (serverErrors.length > 0) {
                    // Refrescar la lista: las facturas con error (ya existe en BC,
                    // fallo de BC) cambian de estado y/o dejan alertas en el servidor.
                    window.filter_init();
                }
            };

            var args = {
                doc_names: JSON.stringify(doc_names)
            };
            if (force) {
                args.force = JSON.stringify(force);
            }

            petition_get_data(args, url, callresponse);
        };

        var validateUrl = "qp_supplier_front.resources.documenteme.approve.validate";

        petition_get_data({
            doc_names: JSON.stringify(doc_names)
        }, validateUrl, function (response) {
            if (response.status !== 200) {
                frappe.msgprint(response.msg);
                return;
            }

            var violations = (response.data && response.data.violations) || [];
            if (violations.length === 0) {
                doApprove(false);
                return;
            }

            var detail = violations.map(function (item) {
                var html = "<li><strong>" + (item.nvfac_nume || "") + "</strong><ul>";
                (item.violations || []).forEach(function (message) {
                    html += "<li>" + message + "</li>";
                });
                html += "</ul></li>";
                return html;
            }).join("");

            frappe.confirm(
                "Las siguientes facturas no cumplen las condiciones de aprobaci&oacute;n autom&aacute;tica:<br><ul>" + detail + "</ul>&iquest;Desea continuar con la aprobaci&oacute;n de todas las facturas seleccionadas?",
                function () {
                    doApprove(true);
                },
                function () {
                    // Cancelar: no se aprueba nada, la selecci&oacute;n queda intacta.
                }
            );
        });
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
        var tooltip = $(this).attr("title");
        if (tooltip && tooltip !== "Alerta") {
            frappe.msgprint(tooltip);
        }
    });

    $(document).on("click", ".btn-control-assign", function () {
        assignTargetDoc = $(this).data("name");
        $("#assign_invoice_modal_label").text("Asignar Factura");

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
            doc_names: JSON.stringify([assignTargetDoc])
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
                    $(this).closest("tr").find(".status-badge")
                        .removeClass("status-open status-ready status-paid status-default status-cancelled")
                        .addClass("status-progress")
                        .text("En proceso de rechazo");
                    $(this).prop("checked", false);
                });
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
        var targetDoc = assignTargetDoc;
        if (targetDoc) {
            doc_names.push(targetDoc);
        } else {
            $('tbody input[type="checkbox"]:checked').each(function () {
                doc_names.push($(this).val());
            });
        }

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
                if (targetDoc) {
                    var $btn = $('.btn-control-assign[data-name="' + targetDoc + '"]');
                    $btn.css("color", "#007bff");
                    $btn.attr("title", "Asignado a:\n- " + userName);
                } else {
                    $('tbody input[type="checkbox"]:checked').each(function () {
                        var $btn = $(this).closest("tr").find(".btn-control-assign");
                        $btn.css("color", "#007bff");
                        $btn.attr("title", "Asignado a:\n- " + userName);
                    });
                    $('tbody input[type="checkbox"]:checked').prop("checked", false);
                }
            }
            assignTargetDoc = null;
        };

        petition_get_data({
            doc_names: JSON.stringify(doc_names),
            user: user
        }, url, callresponse);
    });

    $("#assign_invoice_modal").on("hidden.bs.modal", function () {
        assignTargetDoc = null;
    });

    $("#refresh_filter_list").off("click");
    $("#refresh_filter_list").on("click", function () {
        var $btn = $(this);
        $btn.prop("disabled", true);

        frappe.confirm(
            "Se realizar\u00e1 la sincronizaci\u00f3n de facturas. Puede tardar unos segundos. \u00bfDesea continuar?",
            function () {
                var overlayEl = document.getElementById("overlay");
                var savedOnClick = overlayEl.onclick;
                overlayEl.onclick = null;
                overlayEl.style.display = "block";

                var url = "qp_supplier_front.uses_cases.documents.sync_all_whitelist.refresh_documents";

                var callresponse = (response) => {
                    overlayEl.onclick = savedOnClick;
                    overlayEl.style.display = "none";
                    $btn.prop("disabled", false);
                    if (response && response.success) {
                        $(".filter-list").not("select").val("");
                        $(".filter-list.filter-check").val("0");
                        $(".filter-list.date").removeAttr("min").removeAttr("max");
                        $("select.filter-list").val("0");
                        window.filter_init();
                        frappe.msgprint("Sincronizaci\u00f3n completada.");
                    } else if (response && response.skipped) {
                        frappe.msgprint("Ya hay una sincronizaci\u00f3n en curso.");
                    } else {
                        frappe.msgprint(response && response.error ? response.error : "Error en la sincronizaci\u00f3n de facturas.");
                    }
                };

                petition_get_data({}, url, callresponse);
            },
            function () {
                $btn.prop("disabled", false);
            }
        );
    });

    // =====================================================================
    // Banco de recepciones: seleccion manual con "Aplicar"
    // =====================================================================
    function fmtMoney(value) {
        var n = parseFloat(value) || 0;
        return "$" + n.toLocaleString("es-CO", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        });
    }

    function receiptBankState($bank) {
        var stot = parseFloat($bank.attr("data-stot")) || 0;
        var sum = 0;
        var count = 0;
        $bank.find(".receipt-select:checked").each(function () {
            sum += parseFloat($(this).attr("data-amount")) || 0;
            count++;
        });
        var epsilon = 0.01;
        var classification;
        if (sum > stot + epsilon) {
            classification = "excede";
        } else if (Math.abs(sum - stot) <= epsilon) {
            classification = "completo";
        } else {
            classification = "parcial";
        }
        return { sum: sum, count: count, stot: stot, classification: classification };
    }

    var RECEIPT_CLASS_LABELS = {
        completo: "Completo",
        parcial: "Parcial",
        excede: "Excede el total"
    };
    var RECEIPT_CLASS_COLORS = {
        completo: "#28a745",
        parcial: "#ffc107",
        excede: "#dc3545"
    };

    function renderReceiptBank($bank) {
        if ($bank.length === 0) {
            return;
        }
        var state = receiptBankState($bank);
        $bank.find(".receipt-selected-sum").text(
            fmtMoney(state.sum) + " / " + fmtMoney(state.stot)
        );
        var $badge = $bank.find(".receipt-classification");
        $badge.text(RECEIPT_CLASS_LABELS[state.classification] || "");
        $badge.css("background-color", RECEIPT_CLASS_COLORS[state.classification] || "#6c757d");
        $badge.css("color", "#fff");

        $bank.find(".receipt-apply").prop(
            "disabled",
            state.classification === "excede" || state.count === 0
        );

        // Completo: ya se cubre el total; bloquea marcar mas recibos.
        $bank.find(".receipt-select").each(function () {
            var $chk = $(this);
            if (!$chk.prop("checked") && state.classification === "completo") {
                $chk.prop("disabled", true);
            } else if (!$chk.hasClass("force-disabled")) {
                $chk.prop("disabled", false);
            }
        });
    }

    function initReceiptBanks() {
        $(".receipt-bank").each(function () {
            renderReceiptBank($(this));
        });
    }

    $(document).on("change", ".receipt-select", function () {
        renderReceiptBank($(this).closest(".receipt-bank"));
    });

    $(document).on("click", ".receipt-apply", function () {
        var $bank = $(this).closest(".receipt-bank");
        var docName = $bank.attr("data-doc");
        var state = receiptBankState($bank);
        var receiptNames = [];
        $bank.find(".receipt-select:checked").each(function () {
            receiptNames.push($(this).val());
        });

        if (state.classification === "excede") {
            frappe.msgprint("La selecci\u00f3n excede el total de la factura; desmarque recibos para aplicar.");
            return;
        }
        if (receiptNames.length === 0) {
            frappe.msgprint("Seleccione al menos un recibo para aplicar.");
            return;
        }

        var msg;
        if (state.classification === "completo") {
            msg = "Al confirmar se aprobar\u00e1 autom\u00e1ticamente la factura con " +
                state.count + " recibo(s) seleccionado(s), se iniciar\u00e1 el proceso de aprobaci\u00f3n y los recibos quedar\u00e1n vinculados definitivamente. \u00bfDesea continuar?";
        } else {
            msg = "El monto seleccionado (" + fmtMoney(state.sum) + ") no cubre el total de la factura (" +
                fmtMoney(state.stot) + "). Al confirmar, los recibos quedar\u00e1n reservados para esta factura y no estar\u00e1n disponibles para otras. \u00bfDesea continuar?";
        }

        frappe.confirm(msg, function () {
            var overlayEl = document.getElementById("overlay");
            var savedOnClick = overlayEl ? overlayEl.onclick : null;
            if (overlayEl) {
                overlayEl.onclick = null;
                overlayEl.style.display = "block";
            }

            petition_get_data({
                doc_name: docName,
                receipt_names: JSON.stringify(receiptNames)
            }, "qp_supplier_front.resources.documenteme.receipt_selection.apply", function (response) {
                if (overlayEl) {
                    overlayEl.onclick = savedOnClick;
                    overlayEl.style.display = "none";
                }
                frappe.msgprint(response.msg);
                if (response.status === 200) {
                    window.filter_init();
                }
            });
        }, function () {
            // Cancelar: la seleccion queda intacta.
        });
    });

    // Render inicial + re-render tras scroll infinito / filtros.
    initReceiptBanks();
    var accordionEl = document.getElementById("accordion");
    if (accordionEl && window.MutationObserver) {
        var receiptBankObserver = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                if (mutation.addedNodes && mutation.addedNodes.length) {
                    $(mutation.addedNodes).find(".receipt-bank").each(function () {
                        renderReceiptBank($(this));
                    });
                }
            });
        });
        receiptBankObserver.observe(accordionEl, { childList: true, subtree: true });
    }

});