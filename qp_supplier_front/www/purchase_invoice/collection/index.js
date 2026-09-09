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
    // Detalle expandible (factura / OC / recepciones)
    // =====================================================================
    // El detalle viene renderizado en el HTML (igual que documenteme); el
    // acordeon usa data-toggle="collapse". Quitar el handler delegado generico
    // (qp_supplier_front.js) ligado a filas de detalle para esta vista.
    $("#accordion").off("click", ".detail-row");

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

    function renderNotificationEntry(item) {
        var urgent = item.notification_type === "ErrorUrgente";
        var meta = urgent
            ? { label: "Error urgente", color: "#dc3545", icon: "error" }
            : { label: "Alerta", color: "#ff8c00", icon: "warning" };
        var resolved = item.status !== "Abierta";
        var color = resolved ? "#6c757d" : meta.color;
        var statusLabel = resolved ? "Resuelta" : "Abierta";
        var icon = resolved ? "check_circle" : meta.icon;
        return "<div class=\"ci-notification-entry\">" +
            "<span class=\"ci-notification-dot\" style=\"border-color:" + color + "\">" +
            "<span class=\"material-symbols-outlined\" style=\"color:" + color + "\">" + icon + "</span>" +
            "</span>" +
            "<div style=\"font-size:13px\">" +
            "<div style=\"color:#333;font-weight:bold;font-size:12px;margin-bottom:2px\">" +
                escapeHtml(meta.label) +
                " <span style=\"font-size:11px;color:#8a9099;font-weight:normal\">&middot; " +
                    formatNotificationDate(item.notification_date) + "</span>" +
                " <span style=\"font-size:11px;color:#8a9099;font-weight:normal\">(" +
                    escapeHtml(statusLabel) + ")</span>" +
            "</div>" +
            "<div style=\"color:#444;white-space:pre-wrap;word-break:break-word\">" +
                escapeHtml(item.notification_message) + "</div>" +
            "</div></div>";
    }

    function renderAlertList(alerts) {
        var $el = $("#ci-notification-alerts");
        $el.empty();
        if (!alerts || alerts.length === 0) {
            $el.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin alertas abiertas.</div>");
            return;
        }
        var html = "";
        alerts.forEach(function (item) {
            html += renderNotificationEntry(item);
        });
        $el.html(html);
    }

    function renderHistoryList(history) {
        var $el = $("#ci-notification-history");
        $el.empty();
        if (!history || history.length === 0) {
            $el.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin historial.</div>");
            return;
        }
        var html = "";
        history.forEach(function (item) {
            html += renderNotificationEntry(item);
        });
        $el.html(html);
    }

    $(".btn-control-alert").off("click");
    $(document).on("click", ".btn-control-alert", function (event) {
        event.stopPropagation();
        var docName = $(this).data("name");
        $("#ci-notification-alerts").html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Cargando...</div>");
        $("#ci-notification-history").html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Cargando...</div>");
        $("#ci_notifications_modal").modal("show");

        petition_get_data({
            doc_name: docName
        }, "qp_supplier_front.resources.collection_accounts.collection_invoices.get_notifications", function (response) {
            if (!response || response.status !== 200) {
                $("#ci-notification-history").html("<div style=\"color:#dc3545;font-size:12px;text-align:center;padding:12px\">" +
                    escapeHtml((response && response.msg) || "Error al obtener notificaciones") + "</div>");
                return;
            }
            var data = response.data || {};
            renderAlertList(data.alerts);
            renderHistoryList(data.history);
        });
    });

    $("#ci_notifications_modal").on("hidden.bs.modal", function () {
        $("#ci-notification-alerts").empty();
        $("#ci-notification-history").empty();
    });

    // =====================================================================
    // Comentarios / observaciones (modal timeline.html)
    // =====================================================================
    var timelineDocName = null;

    function renderCommentList(entries) {
        var $list = $("#timeline-list");
        $list.empty();
        if (!entries || entries.length === 0) {
            $list.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin comentarios.</div>");
            return;
        }
        var html = "";
        entries.forEach(function (entry) {
            html += "<div class=\"timeline-entry\">" +
                "<span class=\"timeline-dot\" style=\"border-color:#28a745\">" +
                "<span class=\"material-symbols-outlined\" style=\"color:#28a745\">comment</span>" +
                "</span>" +
                "<div style=\"font-size:13px\">" +
                "<div style=\"color:#333;font-weight:bold;font-size:12px;margin-bottom:2px\">" +
                    escapeHtml(entry.entry_by || "") +
                    " <span style=\"color:#8a9099;font-weight:normal\">&middot; " +
                    formatNotificationDate(entry.entry_date) + "</span>" +
                "</div>" +
                "<div style=\"color:#444;white-space:pre-wrap;word-break:break-word\">" +
                    escapeHtml(entry.message || "") + "</div>" +
                "</div></div>";
        });
        $list.html(html);
    }

    function updateCommentButton(docName, hasUnread) {
        var $btn = $('.btn-control-timeline[data-name="' + docName + '"]');
        if ($btn.length) {
            $btn.css("color", hasUnread ? "#004D90" : "#6c757d");
        }
    }

    function loadConversation(docName, callback) {
        petition_get_data({
            doc_name: docName
        }, "qp_supplier_front.resources.collection_accounts.comments.get_conversation", function (response) {
            if (response.status === 200) {
                var data = response.data || {};
                renderCommentList(data.comments);
                var unread = data.unread_count || 0;
                $("#timeline_unread_hint").text(
                    unread > 0 ? unread + " comentario(s) sin leer" : ""
                );
                updateCommentButton(docName, false);
            } else {
                frappe.msgprint(response.msg || "Error al obtener la conversaci\u00f3n");
            }
            if (callback) {
                callback();
            }
        });
    }

    function markConversationRead(docName) {
        petition_get_data({
            doc_name: docName
        }, "qp_supplier_front.resources.collection_accounts.comments.mark_conversation_read", function (response) {
            if (response.status === 200) {
                var unread = (response.data && response.data.unread_count > 0)
                    ? response.data.unread_count
                    : 0;
                $("#timeline_unread_hint").text(unread > 0 ? unread + " comentario(s) sin leer" : "");
                updateCommentButton(docName, unread > 0);
            }
        });
    }

    $(document).on("click", ".btn-control-timeline", function (event) {
        event.stopPropagation();
        timelineDocName = $(this).data("name");
        $("#timeline_comment_text").val("");
        $("#confirm-timeline-comment").prop("disabled", true);
        $("#timeline_unread_hint").text("");
        loadConversation(timelineDocName, function () {
            $("#timeline_invoice_modal").modal("show");
            markConversationRead(timelineDocName);
        });
    });

    $("#timeline_comment_text").on("input", function () {
        $("#confirm-timeline-comment").prop(
            "disabled",
            String($(this).val() || "").trim() === ""
        );
    });

    $("#timeline_invoice_modal").off("click", "#confirm-timeline-comment");
    $("#confirm-timeline-comment").on("click", function () {
        var comment = String($("#timeline_comment_text").val() || "").trim();
        if (!timelineDocName || !comment) {
            return;
        }
        $("#confirm-timeline-comment").prop("disabled", true);

        petition_get_data({
            doc_name: timelineDocName,
            comment: comment
        }, "qp_supplier_front.resources.collection_accounts.comments.add_comment", function (response) {
            if (response.status === 200) {
                $("#timeline_comment_text").val("");
                renderCommentList(response.data);
                updateCommentButton(timelineDocName, false);
            } else {
                $("#confirm-timeline-comment").prop("disabled", false);
                frappe.msgprint(response.msg || "Error al agregar comentario");
            }
        });
    });

    $("#timeline_invoice_modal").on("hidden.bs.modal", function () {
        timelineDocName = null;
    });

    $(document).on("click", ".btn-control-download", function (event) {
        event.stopPropagation();
        var name = $(this).data("name");
        var nvfacNume = $(this).data("nvfac-nume") || name;
        var url = "/api/method/qp_supplier_front.resources.collection_accounts.collection_invoices.download_files";
        var noCacheUrl = url + "?nocache=" + new Date().getTime() +
                         "&doc_name=" + encodeURIComponent(name) +
                         "&invoice_number=" + encodeURIComponent(nvfacNume);
        window.open(noCacheUrl, "_blank");
    });

    $(document).on("click", ".btn-control-assign", function (event) {
        event.stopPropagation();
        frappe.msgprint("Asignación: pendiente de configuración");
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