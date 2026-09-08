$(document).ready(function () {

    // El scroll infinito generico (qp_supplier_front.js) esta ligado a
    // documenteme; esta vista usa su propio paginador (render_more).
    $(window).off("scroll");

    function fmtFilters() {
        var f = {};

        // Solo facturas generadas desde cuentas de cobro (no del sync BC).
        f["qp_sync_flow"] = "COLLECTION";

        var nit = $("#nvpro_ndoc").val();
        if (nit && String(nit).trim()) {
            f["nvpro_ndoc"] = ["like", String(nit).trim() + "%"];
        }

        var invoice = $("#nvfac_nume").val();
        if (invoice && String(invoice).trim()) {
            f["nvfac_nume"] = ["like", String(invoice).trim() + "%"];
        }

        var status = $("#qp_status").val();
        if (status && status !== "0") {
            f["qp_status"] = status;
        }

        var dateKey = $("#start_date").data("date_key") || "registration_date";
        var start = $("#start_date").val();
        var end = $("#end_date").val();
        if (start && end) {
            f[dateKey] = ["between", [start, end]];
        } else if (start) {
            f[dateKey] = [">=", start];
        } else if (end) {
            f[dateKey] = ["<=", end];
        }

        return f;
    }

    function showOverlay(show) {
        var overlayEl = document.getElementById("overlay");
        if (overlayEl) {
            overlayEl.style.display = show ? "block" : "none";
        }
    }

    function reload() {
        var $accordion = $("#accordion");
        petition_get_data({
            page: 0,
            doctype: $accordion.data("doctype"),
            order_by: $accordion.data("order_by"),
            filters: JSON.stringify(fmtFilters())
        }, "qp_supplier_front.resources.collection_accounts.collection_invoices.render_more", function (response) {
            if (!response || response.status !== 200) {
                frappe.msgprint(response && response.msg ? response.msg : "Error al cargar facturas");
                return;
            }
            $accordion.html(response.data);
            $accordion.find('input[name="seleccion"]').prop("checked", false);
        });
    }

    var debounceTimer = null;
    $(".ci-filter").on("input change", function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(reload, 300);
    });

    $("#refresh_filter_list").on("click", function () {
        reload();
    });

    // =====================================================================
    // Aprobacion (con pre-validacion y confirmacion de violaciones)
    // =====================================================================
    $("#approve-document").on("click", function () {
        var selected = $('tbody input[name="seleccion"]:checked');
        if (selected.length === 0) {
            frappe.msgprint("Seleccione al menos una factura");
            return;
        }

        var doc_names = [];
        selected.each(function () {
            doc_names.push($(this).val());
        });

        var doApprove = function (force) {
            showOverlay(true);
            var args = { doc_names: JSON.stringify(doc_names) };
            if (force) {
                args.force = JSON.stringify(force);
            }

            petition_get_data(args, "qp_supplier_front.resources.collection_accounts.collection_invoices.approve", function (response) {
                showOverlay(false);
                frappe.msgprint(response.msg);
                if (response.status === 200 || (response.data && (response.data.errors || []).length > 0)) {
                    reload();
                }
            });
        };

        petition_get_data({ doc_names: JSON.stringify(doc_names) },
            "qp_supplier_front.resources.collection_accounts.collection_invoices.validate",
            function (response) {
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
                        // Cancelar: la seleccion queda intacta.
                    }
                );
            });
    });

    // =====================================================================
    // Rechazo (sincrono, solo cambia el estado local)
    // =====================================================================
    $("#reject-document").on("click", function () {
        var selected = $('tbody input[name="seleccion"]:checked');
        if (selected.length === 0) {
            frappe.msgprint("Seleccione al menos una factura");
            return;
        }
        $("#reject_invoice_motive").modal("show");
    });

    $("#motive_text").on("input", function () {
        $("#confirm-reject").prop("disabled", $(this).val().trim() === "");
    });

    // =====================================================================
    // Notificaciones (modal del icono de la columna)
    // =====================================================================
    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatNotificationDate(value) {
        if (!value) {
            return "";
        }
        var date = new Date(String(value).replace(" ", "T"));
        if (isNaN(date.getTime())) {
            return value;
        }
        var dd = ("0" + date.getDate()).slice(-2);
        var mm = ("0" + (date.getMonth() + 1)).slice(-2);
        var yyyy = date.getFullYear();
        var hh = ("0" + date.getHours()).slice(-2);
        var min = ("0" + date.getMinutes()).slice(-2);
        return dd + "/" + mm + "/" + yyyy + " " + hh + ":" + min;
    }

    function renderNotificationList(notifications) {
        var $list = $("#ci-notifications-list");
        $list.empty();
        if (!notifications || notifications.length === 0) {
            $list.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin notificaciones.</div>");
            return;
        }
        var html = "";
        notifications.forEach(function (item) {
            var urgent = item.notification_type === "ErrorUrgente";
            var color = urgent ? "#dc3545" : "#ff8c00";
            var statusLabel = item.status === "Abierta" ? "Abierta" : "Resuelta";
            html += "<div style=\"padding:8px 0;border-bottom:1px solid #eee\">" +
                "<div style=\"display:flex;align-items:center;gap:6px\">" +
                "<span style=\"display:inline-block;width:10px;height:10px;border-radius:50%;background:" + color + "\"></span>" +
                "<strong style=\"font-size:12px;color:" + color + "\">" +
                    escapeHtml(urgent ? "Error urgente" : "Alerta") + "</strong>" +
                "<span style=\"font-size:11px;color:#8a9099\">" + formatNotificationDate(item.notification_date) + "</span>" +
                "<span style=\"font-size:11px;color:#8a9099\">(" + escapeHtml(statusLabel) + ")</span>" +
                "</div>" +
                "<div style=\"font-size:12px;color:#444;white-space:pre-wrap;word-break:break-word;margin-top:3px\">" +
                    escapeHtml(item.notification_message) + "</div>" +
            "</div>";
        });
        $list.html(html);
    }

    $(document).on("click", ".btn-control-notification", function () {
        var docName = $(this).data("name");
        $("#ci-notifications-list").html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Cargando...</div>");
        $("#ci_notifications_modal").modal("show");

        petition_get_data({
            doc_name: docName
        }, "qp_supplier_front.resources.collection_accounts.collection_invoices.get_notifications", function (response) {
            if (!response || response.status !== 200) {
                $("#ci-notifications-list").html("<div style=\"color:#dc3545;font-size:12px;text-align:center;padding:12px\">" +
                    escapeHtml((response && response.msg) || "Error al obtener notificaciones") + "</div>");
                return;
            }
            renderNotificationList(response.data);
        });
    });

    $("#ci_notifications_modal").on("hidden.bs.modal", function () {
        $("#ci-notifications-list").empty();
    });

    $("#confirm-reject").on("click", function () {
        var doc_names = [];
        $('tbody input[name="seleccion"]:checked').each(function () {
            doc_names.push($(this).val());
        });
        var motive = $("#motive_text").val().trim();
        var is_invoice_error = $("#is_invoice_error").is(":checked");

        $("#motive_text").val("");
        $("#is_invoice_error").prop("checked", false);
        $("#confirm-reject").prop("disabled", true);
        $("#reject_invoice_motive").modal("hide");

        showOverlay(true);
        petition_get_data({
            doc_names: JSON.stringify(doc_names),
            motive: motive,
            is_invoice_error: JSON.stringify(is_invoice_error)
        }, "qp_supplier_front.resources.collection_accounts.collection_invoices.reject", function (response) {
            showOverlay(false);
            frappe.msgprint(response.msg);
            if (response.status === 200) {
                reload();
            }
        });
    });

});