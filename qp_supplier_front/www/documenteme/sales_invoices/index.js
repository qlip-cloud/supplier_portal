$(document).ready(function () {

    var assignTargetDoc = null;

    $('tbody input[type="checkbox"]').prop("checked", false);

    $("#assign-document").on("click", function () {
        assignTargetDoc = null;
        $("#assign_invoice_modal_label").text("Asignar Facturas");

        var selected = $('tbody input[name="seleccion"]:checked');
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
        var selected = $('tbody input[name="seleccion"]:checked');
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
                    $('tbody input[name="seleccion"]:checked').each(function () {
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
        var selected = $('tbody input[name="seleccion"]:checked');
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
        var name = $(this).data("name");
        $("#notification-alerts").html("<div style=\"color:#8a9099;font-size:12px\">Cargando...</div>");
        $("#notification-summary").empty();
        $("#notification-history").html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Cargando...</div>");
        loadNotifications(name);
        $("#notifications_invoice_modal").modal("show");
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

    // =====================================================================
    // Conversación (comentarios) de facturas documenteme
    // =====================================================================
    var timelineDocName = null;

    var TIMELINE_TYPE_META = {
        creacion: {
            icon: "history",
            color: "#6c757d",
            title: "Registro en el sistema"
        },
        estado: {
            icon: "sync_alt",
            color: "#004D90",
            title: "Cambio de estado"
        },
        comentario: {
            icon: "comment",
            color: "#28a745",
            title: "Comentario"
        }
    };

    var TIMELINE_STATE_LABELS = {
        "A": "Aprobado",
        "E": "Registrado",
        "V": "Lista para Registro",
        "R": "Rechazada",
        "BCC": "Creada en BC",
        "PA": "En proceso de aprobaci\u00f3n",
        "PR": "En proceso de rechazo",
        "T": ""
    };

    function timelineStateLabel(code) {
        return TIMELINE_STATE_LABELS[code] || (code || "-");
    }

    function formatTimelineDate(value) {
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

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function renderTimelineEntry(entry) {
        var meta = TIMELINE_TYPE_META[entry.type] || {
            icon: "history",
            color: "#6c757d",
            title: "Historial"
        };
        var color = meta.color || "#6c757d";
        var isComment = entry.type === "comentario";
        var message = entry.message || "";
        if (entry.type === "estado") {
            message = "Cambio de estado: " + escapeHtml(timelineStateLabel(entry.old_state)) +
                " -> " + escapeHtml(timelineStateLabel(entry.new_state));
        } else {
            message = escapeHtml(message);
        }
        // En los comentarios la linea principal es el autor + fecha (sin la
        // etiqueta "Comentario"); el pie de autor/fecha solo aplica a las
        // demas entradas (creacion/estado).
        var titleLine = isComment
            ? escapeHtml(entry.entry_by || "") + " &middot; " + formatTimelineDate(entry.entry_date)
            : escapeHtml(meta.title || "");
        var footer = isComment
            ? ""
            : "<div style=\"color:#8a9099;font-size:11px;margin-top:3px\">" +
                escapeHtml(entry.entry_by || "") + " &middot; " + formatTimelineDate(entry.entry_date) +
                "</div>";
        var body = "<div class=\"timeline-entry\">" +
            "<span class=\"timeline-dot\" style=\"border-color:" + color + "\">" +
            "<span class=\"material-symbols-outlined\" style=\"color:" + color + "\">" + meta.icon + "</span>" +
            "</span>" +
            "<div style=\"font-size:13px\">" +
            "<div style=\"color:#333;font-weight:bold;font-size:12px;margin-bottom:2px\">" + titleLine + "</div>" +
            "<div style=\"color:#444;white-space:pre-wrap;word-break:break-word\">" + message + "</div>" +
            footer +
            "</div></div>";
        return body;
    }

    function renderCommentList(entries) {
        var $list = $("#timeline-list");
        $list.empty();
        if (!entries || entries.length === 0) {
            $list.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin comentarios.</div>");
            return;
        }
        var html = "";
        entries.forEach(function (entry) {
            html += renderTimelineEntry(entry);
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
        }, "qp_supplier_front.resources.documenteme.timeline.get_conversation", function (response) {
            if (response.status === 200) {
                renderCommentList(response.data.comments);
                var unread = response.data.unread_count || 0;
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
        }, "qp_supplier_front.resources.documenteme.timeline.mark_conversation_read", function (response) {
            if (response.status === 200) {
                $("#timeline_unread_hint").text(
                    (response.data && response.data.unread_count > 0)
                        ? response.data.unread_count + " comentario(s) sin leer"
                        : ""
                );
                updateCommentButton(docName, false);
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

    $("#confirm-timeline-comment").on("click", function () {
        var comment = String($("#timeline_comment_text").val() || "").trim();
        if (!timelineDocName || !comment) {
            return;
        }
        $("#confirm-timeline-comment").prop("disabled", true);

        petition_get_data({
            doc_name: timelineDocName,
            comment: comment
        }, "qp_supplier_front.resources.documenteme.timeline.add_comment", function (response) {
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

    // =====================================================================
    // Notificaciones y alertas (modal del icono de alerta)
    // =====================================================================
    var NOTIF_STATUS_META = {
        ok: { label: "Ok", color: "#28a745", icon: "check_circle" },
        fail: { label: "Error", color: "#dc3545", icon: "error" },
        en_proceso: { label: "En proceso", color: "#ff8c00", icon: "sync" }
    };

    function notifMeta(status) {
        return NOTIF_STATUS_META[status] || {
            label: status || "Desconocido",
            color: "#6c757d",
            icon: "history"
        };
    }

    function renderNotificationSummary(items) {
        var $el = $("#notification-summary");
        $el.empty();
        if (!items || items.length === 0) {
            return;
        }
        var html = "";
        items.forEach(function (item) {
            var meta = notifMeta(item.status);
            html += "<span style=\"display:inline-flex;align-items:center;gap:4px;border:1px solid " + meta.color + ";color:" + meta.color + ";border-radius:4px;padding:2px 8px;font-size:12px;margin:0 6px 6px 0\">" +
                "<span class=\"material-symbols-outlined\" style=\"font-size:14px\">" + meta.icon + "</span>" +
                "<strong>" + escapeHtml(item.event_code) + "</strong> " +
                escapeHtml(meta.label) +
                " <span style=\"font-size:11px;opacity:.85\">" + formatTimelineDate(item.date) + "</span>" +
                "</span>";
        });
        $el.html(html);
    }

    function renderNotificationHistory(events, stateEntries) {
        var $el = $("#notification-history");
        $el.empty();
        var items = [];

        (events || []).forEach(function (ev) {
            var meta = notifMeta(ev.status);
            items.push({
                date: ev.date || "",
                html: "<div class=\"notification-entry\">" +
                    "<span class=\"notification-dot\" style=\"border-color:" + meta.color + "\">" +
                    "<span class=\"material-symbols-outlined\" style=\"color:" + meta.color + "\">" + meta.icon + "</span>" +
                    "</span>" +
                    "<div style=\"font-size:13px\">" +
                    "<div style=\"color:#333;font-weight:bold;font-size:12px;margin-bottom:2px\">Evento " + escapeHtml(ev.event_code) + " &mdash; <span style=\"color:" + meta.color + "\">" + escapeHtml(meta.label) + "</span></div>" +
                    "<div style=\"color:#8a9099;font-size:11px\">" + formatTimelineDate(ev.date) + "</div>" +
                    (ev.error_message
                        ? "<div style=\"color:#dc3545;font-size:11px;word-break:break-word\">" + escapeHtml(ev.error_message) + "</div>"
                        : "") +
                    "</div></div>"
            });
        });

        (stateEntries || []).forEach(function (entry) {
            items.push({
                date: entry.entry_date || "",
                html: renderTimelineEntry(entry)
            });
        });

        items.sort(function (a, b) {
            return (b.date < a.date) ? -1 : ((b.date > a.date) ? 1 : 0);
        });

        if (items.length === 0) {
            $el.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin historial.</div>");
            return;
        }
        var html = "";
        items.forEach(function (item) {
            html += item.html;
        });
        $el.html(html);
    }

    function renderAlertList(alerts) {
        var $el = $("#notification-alerts");
        $el.empty();
        if (!alerts || alerts.length === 0) {
            $el.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin alertas abiertas.</div>");
            return;
        }
        var html = "";
        alerts.forEach(function (alert) {
            var urgent = alert.alert_type === "ErrorUrgente";
            var color = urgent ? "#dc3545" : "#ff8c00";
            html += "<div style=\"padding:6px 0;border-bottom:1px solid #eee\">" +
                "<div style=\"color:" + color + ";font-weight:bold;font-size:12px\">" + (urgent ? "Urgente" : "Alerta") + "</div>" +
                "<div style=\"font-size:12px;color:#444;white-space:pre-wrap;word-break:break-word\">" + escapeHtml(alert.alert_message) + "</div>" +
                "<div style=\"color:#8a9099;font-size:11px\">" + formatTimelineDate(alert.alert_date) + "</div>" +
                "</div>";
        });
        $el.html(html);
    }

    function loadNotifications(docName) {
        petition_get_data({
            doc_name: docName
        }, "qp_supplier_front.resources.documenteme.timeline.get_notifications", function (response) {
            if (response.status === 200) {
                renderAlertList(response.data.alerts);
                renderNotificationSummary(response.data.summary);
                renderNotificationHistory(
                    response.data.events,
                    response.data.state_entries
                );
            } else {
                frappe.msgprint(response.msg || "Error al obtener notificaciones");
            }
        });
    }

    $("#notifications_invoice_modal").on("hidden.bs.modal", function () {
        $("#notification-summary").empty();
        $("#notification-history").empty();
        $("#notification-alerts").empty();
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
                $('tbody input[name="seleccion"]:checked').each(function () {
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
            $('tbody input[name="seleccion"]:checked').each(function () {
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
                    $('tbody input[name="seleccion"]:checked').each(function () {
                        var $btn = $(this).closest("tr").find(".btn-control-assign");
                        $btn.css("color", "#007bff");
                        $btn.attr("title", "Asignado a:\n- " + userName);
                    });
                    $('tbody input[name="seleccion"]:checked').prop("checked", false);
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

    function renderReceiptBankFor(element) {
        renderReceiptBank($(element).closest(".receipt-bank"));
    }

    // Fallback robusto accesible desde el onchange inline del checkbox: en
    // algunos flujos (accordion dentro de la fila desplegable) el cambio de
    // estado del check no se propaga por delegacion.
    window.renderReceiptBankFor = renderReceiptBankFor;

    $(document).on("change", ".receipt-select", function () {
        renderReceiptBankFor(this);
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