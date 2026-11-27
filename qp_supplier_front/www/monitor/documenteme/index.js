$(document).ready(function () {

    var assignTargetDoc = null;

    function setAssignUsersMessage(message) {
        $("#assign-user-list").html(
            '<div class="assign-user-empty">' + message + '</div>');
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function loadAssignUsers() {
        setAssignUsersMessage("Cargando usuarios...");
        $("#assign-user-search").val("");

        petition_get_data({}, "qp_supplier_front.resources.documenteme.assign.get_users", function (response) {
            var users = response.data || [];
            if (!users.length) {
                setAssignUsersMessage("No hay usuarios disponibles");
                return;
            }

            var html = "";
            $.each(users, function (index, u) {
                var fullName = (u.first_name || "") + " " + (u.last_name || "");
                fullName = $.trim(fullName).replace(/\s+/g, " ");
                if (!fullName || fullName.indexOf(" ") === -1) {
                    fullName = u.name;
                }
                html += '<label class="assign-user-option">' +
                    '<input type="checkbox" name="assign-user" value="' + escapeHtml(u.name) + '">' +
                    '<span>' + escapeHtml(fullName) + '</span>' +
                    '</label>';
            });

            $("#assign-user-list").html(html);
        });
    }

    function getSelectedAssignUsers() {
        var users = [];
        $("#assign-user-list input[name=\"assign-user\"]:checked").each(function () {
            users.push($(this).val());
        });
        return users;
    }

    function getAssignUserNames(users) {
        var names = [];
        $("#assign-user-list input[name=\"assign-user\"]").each(function () {
            if (users.indexOf($(this).val()) !== -1) {
                names.push($(this).closest("label").find("span").text());
            }
        });
        return names;
    }

    $("#assign-user-search").on("input", function () {
        var term = $.trim($(this).val()).toLowerCase();
        $("#assign-user-list .assign-user-option").each(function () {
            var search = $(this).text().toLowerCase();
            $(this).toggle(!term || search.indexOf(term) !== -1);
        });
    });

    $('tbody input[type="checkbox"]').prop("checked", false);

    $("#go-collections").on("click", function (event) {
        event.preventDefault();
        closeNav();
        var loader = document.getElementById("page-loader");
        if (loader) {
            loader.style.display = "flex";
        }
        setTimeout(function () {
            window.location.href = $(event.currentTarget).attr("href");
        }, 400);
    });

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

        loadAssignUsers();

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
                    var backendUsed = (response.data && response.data.backend) || "BC";
                    var badgeText = backendUsed === "GP" ? "Creada en GP" : "Creada en BC";
                    $('tbody input[name="seleccion"]:checked').each(function () {
                        var $row = $(this).closest("tr");
                        if (approvedNames.indexOf($(this).val()) !== -1) {
                            $row.find(".status-badge")
                                .removeClass("status-open status-ready status-cancelled status-paid")
                                .addClass("status-default")
                                .text(badgeText);
                        }
                        $(this).prop("checked", false);
                    });
                }
                var serverErrors = (response.data && response.data.errors) || [];
                var pendingSuper = (response.data && response.data.pending_super) || [];
                if (serverErrors.length > 0 || pendingSuper.length > 0) {
                    // Refrescar la lista: las facturas con error (ya existe en BC,
                    // fallo de BC) o pendientes de superaprobacion cambian de estado
                    // y/o dejan alertas en el servidor.
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

            var renderViolations = function (items) {
                return items.map(function (item) {
                    var html = "<li><strong>" + (item.nvfac_nume || "") + "</strong><ul>";
                    (item.violations || []).forEach(function (message) {
                        html += "<li>" + message + "</li>";
                    });
                    html += "</ul></li>";
                    return html;
                }).join("");
            };

            var blocking = violations.filter(function (item) {
                return item.blocking;
            });
            if (blocking.length > 0) {
                frappe.msgprint(
                    "No se puede aprobar las siguientes facturas hasta resolver lo indicado:<br><ul>" +
                    renderViolations(blocking) + "</ul>"
                );
                return;
            }

            var forceable = violations.filter(function (item) {
                return !item.blocking;
            });
            if (forceable.length === 0) {
                doApprove(false);
                return;
            }

            frappe.confirm(
                "Las siguientes facturas no cumplen las condiciones de aprobaci&oacute;n autom&aacute;tica:<br><ul>" + renderViolations(forceable) + "</ul>&iquest;Desea continuar con la aprobaci&oacute;n de todas las facturas seleccionadas?",
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

    $(document).on("click", ".btn-control-alert", function (event) {
        event.stopPropagation();
        var name = $(this).data("name");
        $("#notification-alerts").html("<div style=\"color:#8a9099;font-size:12px\">Cargando...</div>");
        $("#notification-summary").empty();
        $("#notification-history").html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Cargando...</div>");
        loadNotifications(name);
        $("#notifications_invoice_modal").modal("show");
    });

    $(document).on("click", ".btn-control-assign", function (event) {
        event.stopPropagation();
        assignTargetDoc = $(this).data("name");
        $("#assign_invoice_modal_label").text("Asignar Factura");

        var $tbody = $("#assign-table-body");
        $tbody.empty();

        loadAssignUsers();

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

    // =====================================================================
    // Descarga / carga de documentos de la factura
    // =====================================================================
    var URL_ATTACHMENT_STATUS = "qp_supplier_front.resources.documenteme.attachments.get_attachments";
    var URL_ADD_ATTACHMENT = "qp_supplier_front.resources.documenteme.attachments.add_attachment";
    var uploadAttachmentDoc = null;
    var uploadAttachmentFile = null;

    function openInvoiceDownload(name, nvfacNume) {
        var url = "/api/method/qp_supplier_front.resources.documenteme.download.files";
        var noCacheUrl = url + "?nocache=" + new Date().getTime() +
                         "&doc_name=" + encodeURIComponent(name) +
                         "&invoice_number=" + encodeURIComponent(nvfacNume);
        window.open(noCacheUrl, "_blank");
    }

    function renderUploadCurrentFiles(attachments) {
        var $wrapper = $("#upload_invoice_file_current_wrapper");
        var $list = $("#upload_invoice_file_current");
        var rows = attachments || [];
        $list.empty();
        if (!rows.length) {
            $wrapper.hide();
            return;
        }
        rows.forEach(function (file) {
            var label = file.file_name || "documento";
            var type = file.file_type ? " (" + file.file_type + ")" : "";
            if (file.file_url) {
                $list.append($("<a>")
                    .attr("href", file.file_url)
                    .attr("target", "_blank")
                    .attr("rel", "noopener")
                    .text(label + type)
                    .css({
                        display: "block",
                        fontSize: "12px",
                        color: "#004D90",
                        textDecoration: "none"
                    }));
            } else {
                $list.append($("<span>")
                    .text(label + type)
                    .css({ display: "block", fontSize: "12px", color: "#444" }));
            }
        });
        $wrapper.show();
    }

    function resetUploadFileInput() {
        uploadAttachmentFile = null;
        $("#upload_invoice_file_input").val("");
        $("#upload_invoice_file_name").text("");
        $("#upload_invoice_file_clear").hide();
        $("#upload_invoice_file_submit").prop("disabled", true);
    }

    function openUploadAttachmentModal(name, nvfacNume, attachments) {
        uploadAttachmentDoc = name;
        resetUploadFileInput();
        $("#upload_invoice_file_error").hide().text("");
        $("#upload-invoice-file-context").html(
            "Factura <strong>" + escapeHtml(nvfacNume) + "</strong>. " +
            "No hay documentos descargables; cargue el archivo."
        );
        renderUploadCurrentFiles(attachments);
        $("#upload_invoice_file_modal").modal("show");
    }

    $(document).on("click", ".btn-control-download", function (event) {
        event.stopPropagation();
        var name = $(this).data("name");
        var nvfacNume = $(this).data("nvfac-nume");
        var locked = String($(this).data("locked")) === "1";
        petition_get_data({ doc_name: name }, URL_ATTACHMENT_STATUS, function (response) {
            if (response && response.status === 200 && response.data) {
                if (response.data.has_downloadable) {
                    openInvoiceDownload(name, nvfacNume);
                } else if (locked) {
                    frappe.msgprint(
                        "La factura está cerrada y no admite adjuntos");
                } else {
                    openUploadAttachmentModal(
                        name, nvfacNume, response.data.attachments || []);
                }
                return;
            }
            openInvoiceDownload(name, nvfacNume);
        });
    });

    $("#upload_invoice_file_trigger").on("click", function (event) {
        event.preventDefault();
        $("#upload_invoice_file_input").trigger("click");
    });

    $("#upload_invoice_file_clear").on("click", function (event) {
        event.preventDefault();
        resetUploadFileInput();
    });

    $("#upload_invoice_file_input").on("change", function () {
        uploadAttachmentFile = (this.files && this.files[0]) || null;
        $("#upload_invoice_file_name").text(
            uploadAttachmentFile ? uploadAttachmentFile.name : "");
        $("#upload_invoice_file_clear").toggle(!!uploadAttachmentFile);
        $("#upload_invoice_file_submit").prop("disabled", !uploadAttachmentFile);
    });

    $("#upload_invoice_file_submit").on("click", function () {
        if (!uploadAttachmentDoc || !uploadAttachmentFile) {
            return;
        }
        var $button = $(this);
        $button.prop("disabled", true);
        $("#upload_invoice_file_error").hide().text("");
        uploadPublicFile(uploadAttachmentFile).then(function (uploaded) {
            if (!uploaded || !uploaded.file_url) {
                throw new Error("upload_failed");
            }
            petition_get_data({
                doc_name: uploadAttachmentDoc,
                file_id: uploaded.file_id,
                file_url: uploaded.file_url,
                file_name: uploaded.file_name
            }, URL_ADD_ATTACHMENT, function (response) {
                if (!response || response.status !== 200) {
                    $("#upload_invoice_file_error")
                        .text((response && response.msg) || "No se pudo guardar el archivo.")
                        .show();
                    $button.prop("disabled", false);
                    return;
                }
                var docName = uploadAttachmentDoc;
                $("#upload_invoice_file_modal").modal("hide");
                frappe.msgprint({
                    title: "Listo",
                    message: "El documento se carg\u00f3 correctamente.",
                    indicator: "green"
                });
                refreshInvoiceRow(docName);
            });
        }).catch(function () {
            $("#upload_invoice_file_error")
                .text("No se pudo subir el archivo.")
                .show();
            $button.prop("disabled", false);
        });
    });

    // =====================================================================
    // Conversación (comentarios) de facturas documenteme
    // =====================================================================
    var timelineDocName = null;
    var timelineCanSendToBc = false;
    var timelineNewAttachment = null;
    var timelineChangeEntry = null;

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
        },
        asignacion: {
            icon: "shopping_cart",
            color: "#004D90",
            title: "Asignaci\u00f3n de OC"
        },
        asignacion_usuario: {
            icon: "person_add",
            color: "#004D90",
            title: "Asignaci\u00f3n manual"
        },
        documenteme: {
            icon: "cloud_sync",
            color: "#6c757d",
            title: "Documenteme"
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
        "PSA": "Por Autorización",
        "SR": "Sin referencia",
        "FE": "Cerrada",
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

    // Sube un archivo como File publico (is_private=0) para que la URL sea
    // consultable sin login (BC la recibe en el comentario).
    function uploadPublicFile(file) {
        return new Promise(function (resolve, reject) {
            if (!file) {
                resolve(null);
                return;
            }
            var formData = new FormData();
            formData.append("file", file);
            formData.append("is_private", "0");
            fetch("/api/method/upload_file", {
                method: "POST",
                body: formData,
                headers: {
                    "X-Frappe-CSRF-Token": frappe.csrf_token
                }
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error("upload_failed");
                }
                return response.json();
            }).then(function (data) {
                var message = (data && data.message) || {};
                resolve({
                    file_id: message.name || "",
                    file_url: message.file_url || "",
                    file_name: message.file_name || file.name
                });
            }).catch(reject);
        });
    }

    function attachmentIcon(icon, title, cls, entryName, color) {
        return "<a href=\"#\" class=\"" + cls + "\" data-entry=\"" + escapeHtml(entryName || "") +
            "\" title=\"" + title + "\" style=\"color:" + color + ";margin-left:8px;text-decoration:none\">" +
            "<span class=\"material-symbols-outlined\" style=\"font-size:16px;vertical-align:middle\">" +
            icon + "</span></a>";
    }

    function renderAttachmentControls(entry, canSendToBc) {
        var url = entry.attachment_file_url || "";
        var name = entry.attachment_file_name || "";
        var entryName = entry.name || "";
        var icons = "";
        if (url) {
            icons += "<a href=\"" + escapeHtml(url) + "\" target=\"_blank\" rel=\"noopener\" " +
                "title=\"Ver adjunto\" style=\"color:#004D90;margin-left:8px;text-decoration:none\">" +
                "<span class=\"material-symbols-outlined\" style=\"font-size:16px;vertical-align:middle\">visibility</span></a>";
        }
        if (canSendToBc) {
            var changeLabel = url ? "Cambiar archivo" : "Adjuntar archivo";
            icons += "<a href=\"#\" class=\"comment-attachment-change\" data-entry=\"" +
                escapeHtml(entryName) + "\" title=\"" + changeLabel +
                "\" style=\"color:#6c757d;margin-left:8px;text-decoration:none\">" +
                "<span class=\"material-symbols-outlined\" style=\"font-size:16px;vertical-align:middle\">" +
                (url ? "swap_horiz" : "attach_file") + "</span> " + changeLabel + "</a>";
            if (url) {
                icons += attachmentIcon(
                    "close", "Quitar adjunto",
                    "comment-attachment-remove", entryName, "#dc3545"
                );
            }
        }
        if (!url && !canSendToBc) {
            return "";
        }
        var label = name
            ? "<span style=\"color:#8a9099\">" + escapeHtml(name) + "</span>"
            : "";
        return "<div style=\"margin-top:3px;font-size:11px\">" + label + icons + "</div>";
    }

    function renderTimelineEntry(entry, canSendToBc) {
        var meta = TIMELINE_TYPE_META[entry.type] || {
            icon: "history",
            color: "#6c757d",
            title: "Historial"
        };
        var color = meta.color || "#6c757d";
        var isComment = entry.type === "comentario";
        var isAutomatic = entry.origin === "automatic";
        var isManual = entry.origin === "manual";
        var title = meta.title || "Historial";
        // Las asignaciones y los cambios de estado se muestran segun su
        // origen: el flujo automatico no debe aparecer como una accion
        // manual del usuario que disparo el "Actualizar".
        if (entry.type === "asignacion_usuario" || entry.type === "asignacion") {
            title = isAutomatic ? "Asignaci\u00f3n autom\u00e1tica" : "Asignaci\u00f3n manual";
        } else if (entry.type === "estado") {
            title = isAutomatic ? "Cambio de estado autom\u00e1tico" : (isManual ? "Cambio de estado manual" : "Cambio de estado");
        }
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
            : escapeHtml(title);
        var originBadge = "";
        if (!isComment && (isAutomatic || isManual)) {
            originBadge = "<span style=\"display:inline-block;margin-left:6px;padding:1px 6px;border-radius:8px;font-size:10px;font-weight:normal;color:#fff;background-color:" +
                (isAutomatic ? "#6c757d" : "#004D90") + "\">" +
                (isAutomatic ? "Autom\u00e1tico" : "Manual") + "</span>";
        }
        // Check "Enviar a BC" (solo comentarios y solo si la factura aun puede
        // enviarse a BC). Marca el comentario que viajara en el payload BC.
        var bcCheck = "";
        if (isComment && canSendToBc) {
            bcCheck = "<label style=\"float:right;font-weight:normal;font-size:11px;color:#004D90;margin:0;cursor:pointer\">" +
                "<input type=\"checkbox\" class=\"bc-comment-check\" data-entry=\"" + escapeHtml(entry.name || "") + "\"" +
                (entry.send_to_bc ? " checked" : "") +
                " style=\"vertical-align:middle;margin-right:3px\">Enviar a BC</label>";
        }
        var footer = isComment
            ? ""
            : "<div style=\"color:#8a9099;font-size:11px;margin-top:3px\">" +
                escapeHtml(entry.entry_by || "") + " &middot; " + formatTimelineDate(entry.entry_date) +
                "</div>";
        var attachControls = isComment
            ? renderAttachmentControls(entry, canSendToBc)
            : "";
        var body = "<div class=\"timeline-entry\">" +
            "<span class=\"timeline-dot\" style=\"border-color:" + color + "\">" +
            "<span class=\"material-symbols-outlined\" style=\"color:" + color + "\">" + meta.icon + "</span>" +
            "</span>" +
            "<div style=\"font-size:13px\">" +
            "<div style=\"color:#333;font-weight:bold;font-size:12px;margin-bottom:2px\">" + titleLine + originBadge + bcCheck + "</div>" +
            "<div style=\"color:#444;white-space:pre-wrap;word-break:break-word\">" + message + "</div>" +
            attachControls +
            footer +
            "</div></div>";
        return body;
    }

    function renderCommentList(entries, canSendToBc) {
        var $list = $("#timeline-list");
        $list.empty();
        if (!entries || entries.length === 0) {
            $list.html("<div style=\"color:#8a9099;font-size:12px;text-align:center;padding:12px\">Sin comentarios.</div>");
            return;
        }
        var html = "";
        entries.forEach(function (entry) {
            html += renderTimelineEntry(entry, canSendToBc);
        });
        $list.html(html);
    }

    function updateCommentButton(docName, hasUnread) {
        var $btn = $('.btn-control-timeline[data-name="' + docName + '"]');
        if ($btn.length) {
            $btn.css("color", hasUnread ? "#004D90" : "#6c757d");
        }
    }

    function resetNewAttachment() {
        timelineNewAttachment = null;
        $("#timeline_new_attachment_input").val("");
        $("#timeline_new_attachment_name").text("");
        $("#timeline_new_attachment_remove").hide();
        updateConfirmCommentButton();
    }

    function updateConfirmCommentButton() {
        var hasText = String($("#timeline_comment_text").val() || "").trim() !== "";
        var hasAttachment = !!timelineNewAttachment;
        $("#confirm-timeline-comment").prop(
            "disabled", !timelineDocName || !(hasText || hasAttachment)
        );
    }

    // "Enviar a BC" marcado por defecto si ningun comentario lo esta (solo un
    // comentario puede viajar a BC a la vez).
    function updateDefaultBcCheckbox(comments) {
        var hasMarked = (comments || []).some(function (comment) {
            return !!comment.send_to_bc;
        });
        $("#timeline_send_to_bc").prop(
            "checked", timelineCanSendToBc && !hasMarked
        );
    }

    function loadConversation(docName, callback) {
        petition_get_data({
            doc_name: docName
        }, "qp_supplier_front.resources.documenteme.timeline.get_conversation", function (response) {
            if (response.status === 200) {
                timelineCanSendToBc = !!(response.data && response.data.can_send_to_bc);
                renderCommentList(response.data.comments, timelineCanSendToBc);
                updateDefaultBcCheckbox(response.data.comments);
                $("#timeline_send_to_bc_wrapper").toggle(timelineCanSendToBc);
                $("#timeline_attachment_wrapper").toggle(timelineCanSendToBc);
                resetNewAttachment();
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
        resetNewAttachment();
        loadConversation(timelineDocName, function () {
            $("#timeline_invoice_modal").modal("show");
            markConversationRead(timelineDocName);
        });
    });

    $("#timeline_comment_text").on("input", function () {
        updateConfirmCommentButton();
    });

    // Adjunto del nuevo comentario: seleccion / quitar.
    $("#timeline_attach_trigger").on("click", function (event) {
        event.preventDefault();
        $("#timeline_new_attachment_input").trigger("click");
    });

    $("#timeline_new_attachment_input").on("change", function () {
        timelineNewAttachment = (this.files && this.files[0]) || null;
        $("#timeline_new_attachment_name").text(
            timelineNewAttachment ? timelineNewAttachment.name : ""
        );
        $("#timeline_new_attachment_remove").toggle(!!timelineNewAttachment);
        updateConfirmCommentButton();
    });

    $("#timeline_new_attachment_remove").on("click", function (event) {
        event.preventDefault();
        resetNewAttachment();
    });

    $("#confirm-timeline-comment").on("click", function () {
        var comment = String($("#timeline_comment_text").val() || "").trim();
        if (!timelineDocName || (!comment && !timelineNewAttachment)) {
            return;
        }
        $("#confirm-timeline-comment").prop("disabled", true);
        var attachment = timelineNewAttachment;

        uploadPublicFile(attachment).then(function (file) {
            petition_get_data({
                doc_name: timelineDocName,
                comment: comment,
                send_to_bc: JSON.stringify(
                    timelineCanSendToBc && $("#timeline_send_to_bc").is(":checked")
                ),
                attachment_file_id: file ? file.file_id : "",
                attachment_file_url: file ? file.file_url : "",
                attachment_file_name: file ? file.file_name : ""
            }, "qp_supplier_front.resources.documenteme.timeline.add_comment", function (response) {
                if (response.status === 200) {
                    $("#timeline_comment_text").val("");
                    resetNewAttachment();
                    renderCommentList(response.data, timelineCanSendToBc);
                    updateDefaultBcCheckbox(response.data);
                    updateCommentButton(timelineDocName, false);
                } else {
                    updateConfirmCommentButton();
                    frappe.msgprint(response.msg || "Error al agregar comentario");
                }
            });
        }).catch(function () {
            updateConfirmCommentButton();
            frappe.msgprint("Error al subir el archivo adjunto");
        });
    });

    // Cambiar / quitar el adjunto de un comentario existente (aunque no este
    // marcado "Enviar a BC"). El archivo se sube como publico y se reemplaza.
    $(document).on("click", ".comment-attachment-change", function (event) {
        event.preventDefault();
        timelineChangeEntry = $(this).data("entry");
        $("#timeline_change_attachment_input").val("").trigger("click");
    });

    $("#timeline_change_attachment_input").on("change", function () {
        var entryName = timelineChangeEntry;
        var file = (this.files && this.files[0]) || null;
        $("#timeline_change_attachment_input").val("");
        timelineChangeEntry = null;
        if (!timelineDocName || !entryName || !file) {
            return;
        }
        uploadPublicFile(file).then(function (uploaded) {
            petition_get_data({
                doc_name: timelineDocName,
                entry_name: entryName,
                attachment_file_id: uploaded ? uploaded.file_id : "",
                attachment_file_url: uploaded ? uploaded.file_url : "",
                attachment_file_name: uploaded ? uploaded.file_name : ""
            }, "qp_supplier_front.resources.documenteme.timeline.set_comment_attachment", function (response) {
                if (response.status === 200) {
                    timelineCanSendToBc = !!(response.data && response.data.can_send_to_bc);
                    renderCommentList(response.data.comments, timelineCanSendToBc);
                } else {
                    frappe.msgprint(response.msg || "Error al actualizar el adjunto");
                    loadConversation(timelineDocName);
                }
            });
        }).catch(function () {
            frappe.msgprint("Error al subir el archivo adjunto");
        });
    });

    $(document).on("click", ".comment-attachment-remove", function (event) {
        event.preventDefault();
        var entryName = $(this).data("entry");
        if (!timelineDocName || !entryName) {
            return;
        }
        petition_get_data({
            doc_name: timelineDocName,
            entry_name: entryName,
            attachment_file_id: "",
            attachment_file_url: "",
            attachment_file_name: ""
        }, "qp_supplier_front.resources.documenteme.timeline.set_comment_attachment", function (response) {
            if (response.status === 200) {
                timelineCanSendToBc = !!(response.data && response.data.can_send_to_bc);
                renderCommentList(response.data.comments, timelineCanSendToBc);
            } else {
                frappe.msgprint(response.msg || "Error al quitar el adjunto");
                loadConversation(timelineDocName);
            }
        });
    });

    // Solo un comentario puede marcarse como "Enviar a BC": al marcar uno se
    // desmarcan los demas (el servidor tambien lo garantiza). El mensaje
    // marcado viaja en la key Comentarios del payload BC.
    $(document).on("change", ".bc-comment-check", function () {
        var entryName = $(this).data("entry");
        var checked = $(this).is(":checked");
        if (!timelineDocName || !entryName) {
            return;
        }
        $(".bc-comment-check").not(this).prop("checked", false);
        petition_get_data({
            doc_name: timelineDocName,
            entry_name: entryName,
            flag: JSON.stringify(checked)
        }, "qp_supplier_front.resources.documenteme.timeline.set_bc_comment", function (response) {
            if (response.status === 200) {
                timelineCanSendToBc = !!(response.data && response.data.can_send_to_bc);
                renderCommentList(response.data.comments, timelineCanSendToBc);
                updateDefaultBcCheckbox(response.data.comments);
            } else {
                frappe.msgprint(response.msg || "Error al marcar el comentario");
                loadConversation(timelineDocName);
            }
        });
    });

    $("#timeline_invoice_modal").on("hidden.bs.modal", function () {
        timelineDocName = null;
        timelineCanSendToBc = false;
        timelineChangeEntry = null;
        resetNewAttachment();
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
                        ? "<div style=\"color:" + meta.color + ";font-size:11px;word-break:break-word\">" + escapeHtml(ev.error_message) + "</div>"
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
                $("#motive_text").val("");
                $("#is_invoice_error").prop("checked", false);
                var rejectedDocs = (response.data && response.data.rejected) || [];
                var inProcessDocs = (response.data && response.data.in_process) || [];
                $('tbody input[name="seleccion"]:checked').each(function () {
                    var docName = $(this).val();
                    var $badge = $(this).closest("tr").find(".status-badge");
                    $badge.removeClass("status-open status-ready status-paid status-default status-cancelled status-progress");
                    if (inProcessDocs.indexOf(docName) !== -1) {
                        $badge.addClass("status-progress").text("En proceso de rechazo");
                    } else if (rejectedDocs.indexOf(docName) !== -1) {
                        $badge.addClass("status-cancelled").text("Rechazada");
                    } else {
                        // Respuesta sin desglose (backend previo): conservar
                        // el comportamiento anterior.
                        $badge.addClass("status-progress").text("En proceso de rechazo");
                    }
                    $(this).prop("checked", false);
                });
            } else {
                // El motivo queda en el formulario para que el usuario reintente.
                $("#confirm-reject").prop("disabled", false);
            }
        };

        petition_get_data({
            doc_names: JSON.stringify(doc_names),
            motive: motive,
            is_invoice_error: JSON.stringify(is_invoice_error)
        }, url, callresponse);
    });

    // =====================================================================
    // Cierre / reapertura externa (FE) — solo administradores
    // =====================================================================
    function syncExternalConfirmState() {
        var mode = $("#external_status_mode").val();
        var motive = $("#external_status_motive").val().trim();
        var ok = motive !== "";
        if (mode === "close") {
            ok = ok && $("#external_status_confirm").is(":checked");
        }
        $("#confirm-external-status").prop("disabled", !ok);
    }

    $("#external_status_motive").on("input", syncExternalConfirmState);
    $("#external_status_confirm").on("change", syncExternalConfirmState);

    $(document).on("click", ".btn-control-external-close", function (event) {
        event.stopPropagation();
        var $btn = $(this);
        $("#external_status_mode").val("close");
        $("#external_status_doc").val($btn.data("name"));
        $("#external_status_label").text("Cerrar factura");
        $("#confirm-external-status").text("Cerrar");
        $("#external-close-info").show();
        $("#external-reopen-info").hide();
        $("#external-close-confirm-group").show();
        $("#external_status_confirm").prop("checked", false);
        $("#external_status_motive").val("");
        $("#external-close-invoice").text($btn.data("invoice") || "-");
        var supplier = $btn.data("supplier");
        $("#external-close-supplier").text(supplier ? " \u2014 " + supplier : "");
        var total = $btn.data("total");
        $("#external-close-total").text(total ? fmtMoney(total) : "-");
        $("#confirm-external-status").prop("disabled", true);
        $("#external_status_modal").modal("show");
    });

    $(document).on("click", ".btn-control-external-status", function (event) {
        event.stopPropagation();
        var $btn = $(this);
        $("#external_status_mode").val("reopen");
        $("#external_status_doc").val($btn.data("name"));
        $("#external_status_label").text("Factura cerrada");
        $("#confirm-external-status").text("Reabrir");
        $("#external-close-info").hide();
        $("#external-reopen-info").show();
        $("#external-close-confirm-group").hide();
        $("#external_status_confirm").prop("checked", false);
        $("#external_status_motive").val("");
        $("#external-reopen-invoice").text($btn.data("invoice") || "-");
        $("#external-reopen-by").text($btn.data("by") || "-");
        $("#external-reopen-at").text(
            formatTimelineDate($btn.data("at")) || "-");
        $("#external-reopen-prev").text(
            timelineStateLabel($btn.data("prev")) || "-");
        $("#external-reopen-reason").text($btn.data("reason") || "-");
        $("#confirm-external-status").prop("disabled", true);
        $("#external_status_modal").modal("show");
    });

    $("#confirm-external-status").on("click", function () {
        var mode = $("#external_status_mode").val();
        var docName = $("#external_status_doc").val();
        var motive = $("#external_status_motive").val().trim();
        if (!docName || !motive) {
            return;
        }

        $("#confirm-external-status").prop("disabled", true);
        $("#external_status_modal").modal("hide");

        var overlayEl = document.getElementById("overlay");
        var savedOnClick = overlayEl ? overlayEl.onclick : null;
        if (overlayEl) {
            overlayEl.onclick = null;
            overlayEl.style.display = "block";
        }

        var url = mode === "close"
            ? "qp_supplier_front.resources.documenteme.finalize_external.finalize_external"
            : "qp_supplier_front.resources.documenteme.finalize_external.reopen_external";

        callresponse = (response) => {
            if (overlayEl) {
                overlayEl.onclick = savedOnClick;
                overlayEl.style.display = "none";
            }
            frappe.msgprint(response.msg);
            if (response.status === 200) {
                refreshInvoiceRow(docName);
            }
        };

        petition_get_data({
            doc_name: docName,
            motive: motive
        }, url, callresponse);
    });

    $("#confirm-assign").on("click", function () {
        var users = getSelectedAssignUsers();
        if (!users.length) {
            frappe.msgprint("Seleccione al menos un usuario para asignar");
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

        var assignedNames = getAssignUserNames(users);
        var assignedTitle = "Asignado a:\n" + assignedNames.map(function (name) {
            return "- " + name;
        }).join("\n");

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
                    $btn.attr("title", assignedTitle);
                } else {
                    $('tbody input[name="seleccion"]:checked').each(function () {
                        var $btn = $(this).closest("tr").find(".btn-control-assign");
                        $btn.css("color", "#007bff");
                        $btn.attr("title", assignedTitle);
                    });
                    $('tbody input[name="seleccion"]:checked').prop("checked", false);
                }
            }
            assignTargetDoc = null;
        };

        petition_get_data({
            doc_names: JSON.stringify(doc_names),
            users: JSON.stringify(users)
        }, url, callresponse);
    });

    $("#assign_invoice_modal").on("hidden.bs.modal", function () {
        assignTargetDoc = null;
    });

    var SYNC_POLL_MS = 3000;
    var SYNC_POLL_MAX = 200;
    var syncPollCancelled = false;

    var URL_DOCUMENTS_SYNC_STATUS = "qp_supplier_front.uses_cases.documents.sync_all_whitelist.get_documents_sync_status";
    var URL_REFRESH_DOCUMENTS = "qp_supplier_front.uses_cases.documents.sync_all_whitelist.refresh_documents";
    var URL_UNLOCK_DOCUMENTS_SYNC = "qp_supplier_front.uses_cases.documents.sync_all_whitelist.unlock_documents_sync";
    var URL_AUTO_APPROVE_STATUS = "qp_supplier_front.resources.documenteme.auto_approve.get_auto_approve_job_status";
    var URL_AUTO_APPROVE_RETRY = "qp_supplier_front.resources.documenteme.auto_approve.retry_auto_approve";
    var URL_RENDER_ROW = "qp_supplier_front.resources.utils.pagination.render_row";

    // Un solo estado continuo: la barra sigue visible desde el click hasta que
    // terminan el sync y la aprobacion en segundo plano. No se recarga la
    // lista a mitad de camino (eso hacia que pareciera terminado y reiniciara).
    function setSyncProgress(text) {
        $("#refresh_filter_list").prop("disabled", true);
        $("#sync-progress-text").text(text || "Actualizando...");
        $("#sync-progress").css("display", "flex");
    }

    function clearSyncProgress() {
        $("#sync-progress").hide();
        $("#refresh_filter_list").prop("disabled", false);
    }

    function finishRefresh() {
        clearSyncProgress();
        window.filter_init();
        frappe.msgprint("Actualizaci\u00f3n completada.");
    }

    // Las acciones operativas (desbloquear el sync, reintentar la aprobacion)
    // solo se ofrecen al Administrator; el backend tambien valida el permiso.
    function canManageSync() {
        return $("#refresh_filter_list").attr("data-is-administrator") === "1";
    }

    // Mensaje de sincronizacion en curso. El boton "Desbloquear" solo
    // aparece para el Administrator.
    function syncBusyDialog(text) {
        var dialog = {
            title: "Sincronizaci\u00f3n en curso",
            message: text
        };
        if (canManageSync()) {
            dialog.primary_action = {
                label: "Desbloquear",
                action: unlockSyncAndReload
            };
        }
        return dialog;
    }

    // Libera un lock colgado (crash/worker caido) sin esperar el TTL.
    function unlockSyncAndReload() {
        syncPollCancelled = true;
        petition_get_data({}, URL_UNLOCK_DOCUMENTS_SYNC, function (response) {
            if (!response || response.success === false) {
                frappe.msgprint((response && response.error) || "No tiene permiso para desbloquear la sincronizaci\u00f3n.");
                return;
            }
            clearSyncProgress();
            window.filter_init();
            frappe.msgprint("Sincronizaci\u00f3n desbloqueada. Puede actualizar de nuevo.");
        });
    }

    // Espera a que termine la sincronizacion de otro usuario. Cuando el lock
    // se libera puede quedar una aprobacion en segundo plano: se continua con
    // ese estado antes de dar la actualizacion por terminada.
    function pollSyncStatus(attempts) {
        if (syncPollCancelled) {
            return;
        }
        if (attempts >= SYNC_POLL_MAX) {
            clearSyncProgress();
            window.filter_init();
            if (canManageSync()) {
                frappe.msgprint(syncBusyDialog(
                    "La sincronizaci\u00f3n sigue en curso. Actualice la lista cuando termine."
                ));
            } else {
                frappe.msgprint("La actualizaci\u00f3n est\u00e1 tardando m\u00e1s de lo normal. "
                    + "Vuelva a intentarlo en unos minutos.");
            }
            return;
        }
        setSyncProgress("Actualizando facturas...");
        petition_get_data({}, URL_DOCUMENTS_SYNC_STATUS, function (status) {
            if (status && status.locked) {
                setTimeout(function () { pollSyncStatus(attempts + 1); }, SYNC_POLL_MS);
                return;
            }
            petition_get_data({}, URL_AUTO_APPROVE_STATUS, function (approval) {
                if (approval && approval.pending) {
                    pollBackgroundApproval(0);
                    return;
                }
                finishRefresh();
            });
        });
    }

    // Espera la aprobacion en segundo plano manteniendo el estado continuo. Al
    // usuario no se le muestra mecanica interna (worker, cola, conteos): solo
    // un mensaje generico de actualizacion en curso.
    function pollBackgroundApproval(attempts, finishedMessage, refreshFn, progressText) {
        var refresh = refreshFn || window.filter_init;
        if (attempts >= SYNC_POLL_MAX) {
            clearSyncProgress();
            refresh();
            frappe.msgprint("La actualizaci\u00f3n est\u00e1 tardando m\u00e1s de lo normal. "
                + "Vuelva a intentarlo en unos minutos.");
            return;
        }
        petition_get_data({}, URL_AUTO_APPROVE_STATUS, function (status) {
            if (status && status.pending) {
                setSyncProgress(progressText || "Actualizando facturas...");
                setTimeout(function () {
                    pollBackgroundApproval(attempts + 1, finishedMessage, refreshFn, progressText);
                }, SYNC_POLL_MS);
                return;
            }
            clearSyncProgress();
            if (status && status.waiting_worker) {
                refresh();
                if (canManageSync()) {
                    frappe.msgprint({
                        title: "Actualizaci\u00f3n pendiente",
                        message: "La aprobaci\u00f3n autom\u00e1tica no tiene worker activo: "
                            + "el job qued\u00f3 en cola. Inicie el worker o reintente.",
                        primary_action: {
                            label: "Reintentar",
                            action: retryBackgroundApproval
                        }
                    });
                    return;
                }
                frappe.msgprint("La actualizaci\u00f3n est\u00e1 tardando m\u00e1s de lo normal. "
                    + "Vuelva a intentarlo en unos minutos.");
                return;
            }
            refresh();
            frappe.msgprint(finishedMessage || "Actualizaci\u00f3n completada.");
        });
    }

    // Reencola la aprobacion cuando el job quedo colgado sin worker.
    function retryBackgroundApproval() {
        setSyncProgress("Reencolando aprobaci\u00f3n...");
        petition_get_data({}, URL_AUTO_APPROVE_RETRY, function (response) {
            if (response && (response.enqueued > 0 || response.already_queued)) {
                frappe.msgprint("Aprobaci\u00f3n reencolada.");
                pollBackgroundApproval(0);
                return;
            }
            clearSyncProgress();
            if (response && response.error) {
                frappe.msgprint(response.error);
            }
        });
    }

    $("#refresh_filter_list").off("click");
    $("#refresh_filter_list").on("click", function () {
        var $btn = $(this);
        syncPollCancelled = false;
        $btn.prop("disabled", true);

        frappe.confirm(
            "Se realizar\u00e1 la sincronizaci\u00f3n de facturas. Puede tardar unos segundos. \u00bfDesea continuar?",
            function () {
                var overlayEl = document.getElementById("overlay");
                var savedOnClick = overlayEl.onclick;
                overlayEl.onclick = null;
                overlayEl.style.display = "block";
                setSyncProgress("Actualizando facturas...");

                var url = URL_REFRESH_DOCUMENTS;

                var callresponse = (response) => {
                    overlayEl.onclick = savedOnClick;
                    overlayEl.style.display = "none";
                    if (response && response.success) {
                        $(".filter-list").not("select").val("");
                        $(".filter-list.filter-check").val("0");
                        $(".filter-list.date").removeAttr("min").removeAttr("max");
                        $("select.filter-list").val("0");
                        var fetchBlockedMsg = response.fetch_blocked
                            ? "La descarga de facturas nuevas est\u00e1 bloqueada "
                                + "temporalmente. Se actualizaron asignaciones, "
                                + "aprobaciones y rechazos, pero no se trajeron "
                                + "facturas nuevas."
                            : null;
                        if (response.enqueued > 0 || response.already_queued) {
                            // Un solo estado continuo: no se recarga la lista
                            // hasta que termina la aprobacion en segundo plano.
                            setSyncProgress("Actualizando facturas...");
                            if (fetchBlockedMsg) {
                                frappe.msgprint(fetchBlockedMsg);
                            }
                            pollBackgroundApproval(0);
                            return;
                        }
                        if (fetchBlockedMsg) {
                            clearSyncProgress();
                            window.filter_init();
                            frappe.msgprint(fetchBlockedMsg);
                            return;
                        }
                        finishRefresh();
                        return;
                    }
                    if (response && response.skipped) {
                        setSyncProgress("Actualizando facturas...");
                        if (canManageSync()) {
                            frappe.msgprint(syncBusyDialog(
                                "Ya hay una sincronizaci\u00f3n en curso. La lista se "
                                    + "actualizar\u00e1 cuando termine."
                            ));
                        }
                        pollSyncStatus(0);
                        return;
                    }
                    clearSyncProgress();
                    frappe.msgprint(response && response.error ? response.error : "Error en la sincronizaci\u00f3n de facturas.");
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
            state.count === 0
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

        if (receiptNames.length === 0) {
            frappe.msgprint("Seleccione al menos un recibo para aplicar.");
            return;
        }

        var msg;
        if (state.classification === "completo") {
            msg = "Al confirmar se aplicar\u00e1n " + state.count +
                " recibo(s) a la factura (quedar\u00e1n vinculados). \u00bfDesea continuar?";
        } else if (state.classification === "excede") {
            msg = "El valor de las recepciones seleccionadas (" + fmtMoney(state.sum) +
                ") excede el total de la factura (" + fmtMoney(state.stot) +
                "). Las recepciones son indivisibles, por lo que se aplicar\u00e1n completas. \u00bfDesea continuar?";
        } else {
            msg = "El monto seleccionado (" + fmtMoney(state.sum) + ") no cubre el total de la factura (" +
                fmtMoney(state.stot) + "). Los recibos quedar\u00e1n aplicados a esta factura y no estar\u00e1n disponibles para otras. \u00bfDesea continuar?";
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
                // El aviso de exito va como alerta flotante (sin modal ni
                // backdrop): un msgprint abierto junto al modal de detalle
                // dejaba su backdrop por debajo y el modal se seguia viendo.
                if (response.status === 200) {
                    $("#invoice_detail_modal").modal("hide");
                    // Vacia el modal antes de refrescar para no duplicar ids
                    // (receipt-products-*) si la fila vuelve a mostrar el banco.
                    $("#invoice-detail-body").empty();
                    refreshInvoiceRow(docName);
                    frappe.show_alert({
                        message: response.msg,
                        indicator: "green"
                    }, 7);
                    return;
                }
                frappe.msgprint(response.msg);
            });
        }, function () {
            // Cancelar: la seleccion queda intacta.
        });
    });

    // =====================================================================
    // Factura de referencia de NC (devoluciones GP)
    // =====================================================================
    var refNcDocName = null;
    var refNcSelected = null;
    window.__refNcInvoices = [];

    function renderRefCandidates(invoices, search) {
        search = String(search || "").trim().toLowerCase();
        var $body = $("#reference-nc-body");
        $body.empty();
        var rows = (invoices || []).filter(function (inv) {
            if (!search) {
                return true;
            }
            return String(inv.nvfac_nume || inv.detail || inv.invoice_id || inv.name || "")
                .toLowerCase().indexOf(search) !== -1;
        });
        if (rows.length === 0) {
            $body.html('<tr><td colspan="5" class="text-center" style="color:#8a9099">Sin candidatas</td></tr>');
            return;
        }
        var REF_INVOICE_STATE_LABELS = {
            "A": "Aprobada",
            "E": "Registrada",
            "V": "Lista para Registro",
            "R": "Rechazada",
            "BCC": "Creada en GP",
            "PA": "En proceso de aprobaci\u00f3n",
            "PR": "En proceso de rechazo",
            "PSA": "Por Autorización",
            "SR": "Sin referencia",
            "T": ""
        };
        function refInvoiceStateLabel(code) {
            return REF_INVOICE_STATE_LABELS[code] || timelineStateLabel(code);
        }
        rows.forEach(function (inv) {
            var label = inv.referencia || inv.nvfac_nume || inv.detail || inv.invoice_id || inv.name || "";
            var $tr = $("<tr class=\"ref-row\" data-invoice=\"" + escapeHtml(label) + "\">" +
                "<td>" + escapeHtml(inv.nvfac_nume || inv.detail || "-") + "</td>" +
                "<td>" + escapeHtml(inv.invoice_id || "") + "</td>" +
                "<td>" + escapeHtml(inv.registration_date || "") + "</td>" +
                "<td>" + fmtMoney(inv.subtotal) + "</td>" +
                "<td>" + escapeHtml(refInvoiceStateLabel(inv.nvfac_esta)) + "</td>" +
                "</tr>");
            $tr.on("click", function () {
                $(".ref-row").removeClass("selected");
                $tr.addClass("selected");
                refNcSelected = label;
                $("#reference-nc-selected-label").text(label);
                $("#reference-nc-confirm").show();
            });
            $body.append($tr);
        });
    }

    function submitRefAssign(approveFlag) {
        if (!refNcDocName || !refNcSelected) {
            frappe.msgprint("Seleccione una factura de referencia");
            return;
        }
        var overlayEl = document.getElementById("overlay");
        var savedOnClick = overlayEl ? overlayEl.onclick : null;
        if (overlayEl) {
            overlayEl.onclick = null;
            overlayEl.style.display = "block";
        }
        petition_get_data({
            doc_name: refNcDocName,
            invoice_number: refNcSelected,
            approve: JSON.stringify(approveFlag)
        }, "qp_supplier_front.resources.documenteme.nc_reference.assign_reference",
            function (response) {
                if (overlayEl) {
                    overlayEl.onclick = savedOnClick;
                    overlayEl.style.display = "none";
                }
                frappe.msgprint(response.msg);
                if (response.status === 200) {
                    $("#reference_nc_modal").modal("hide");
                    refreshInvoiceRow(refNcDocName);
                }
            }
        );
    }

    function loadRefCandidates(start, end) {
        refNcSelected = null;
        $("#reference-nc-confirm").hide();
        $("#reference-nc-search").val("");
        $("#reference-nc-body").html(
            '<tr><td colspan="5" class="text-center" style="color:#8a9099">Cargando candidatas...</td></tr>'
        );

        var args = { doc_name: refNcDocName };
        if (start) {
            args.start = start;
        }
        if (end) {
            args.end = end;
        }

        petition_get_data(args,
            "qp_supplier_front.resources.documenteme.nc_reference.get_reference_candidates",
            function (response) {
                if (response.status !== 200) {
                    $("#reference-nc-body").html(
                        '<tr><td colspan="5" class="text-center" style="color:#dc3545">' +
                        escapeHtml(response.msg || "Error") + '</td></tr>'
                    );
                    frappe.msgprint(response.msg || "Error al obtener candidatas");
                    return;
                }
                var data = response.data || {};
                window.__refNcInvoices = data.invoices || [];
                $("#reference-nc-start").val(data.start || "");
                $("#reference-nc-end").val(data.end || "");
                renderRefCandidates(window.__refNcInvoices, "");
            }
        );
    }

    $(document).on("click", ".btn-control-reference", function (event) {
        event.stopPropagation();
        refNcDocName = $(this).data("name");
        $("#reference-nc-start").val("");
        $("#reference-nc-end").val("");
        $("#reference_nc_modal").modal("show");
        loadRefCandidates("", "");
    });

    $("#reference-nc-start, #reference-nc-end").on("change", function () {
        loadRefCandidates($("#reference-nc-start").val(), $("#reference-nc-end").val());
    });

    $("#reference-nc-search").on("input", function () {
        renderRefCandidates(window.__refNcInvoices || [], $(this).val());
    });

    // Confirmacion con 3 opciones:
    //  - "No asignar"        -> cancela (sin efectos)
    //  - "Solo asignar"      -> asigna la referencia y deja la NC en "V"
    //  - "Asignar y Aprobar" -> asigna e inicia la aprobacion de inmediato
    $("#reference-nc-no").on("click", function () {
        refNcSelected = null;
        $("#reference_nc_modal").modal("hide");
    });

    $("#reference-nc-assign").on("click", function () {
        submitRefAssign(false);
    });

    $("#reference-nc-approve").on("click", function () {
        submitRefAssign(true);
    });

    // =====================================================================
    // Asignacion manual de la OC (factura de credito sin OC)
    // =====================================================================
    var refPoDocName = null;
    var refPoSelected = {};
    var refPoPreselected = false;
    window.__refPoOrders = [];

    function refreshRefPoCount() {
        var count = Object.keys(refPoSelected).length;
        $("#reference-po-count").text(
            count ? (count + " orden(es) seleccionada(s)") : ""
        );
        $("#reference-po-confirm").toggle(count > 0);
    }

    function toggleRefPo(name) {
        if (refPoSelected[name]) {
            delete refPoSelected[name];
        } else {
            refPoSelected[name] = true;
        }
        $(".ref-po-row").each(function () {
            var order = $(this).attr("data-order");
            var selected = !!refPoSelected[order];
            $(this).toggleClass("selected", selected);
            $(this).find(".ref-po-check").prop("checked", selected);
        });
        refreshRefPoCount();
    }

    // Preselecciona las OC que la factura ya tiene agregadas manualmente para
    // que al reabrir el modal se sumen nuevas ordenes sin reemplazar las
    // existentes. Solo corre una vez por apertura: respeta lo que el usuario
    // destilda al cambiar los filtros.
    function preselectRefPo(orders) {
        (orders || []).forEach(function (name) {
            if (name) {
                refPoSelected[name] = true;
            }
        });
    }

    function renderRefPoDeclared(orders) {
        var $notice = $("#reference-po-declared");
        var declared = (orders || []).filter(function (order) {
            return !!order;
        });
        if (declared.length === 0) {
            $notice.hide().empty();
            return;
        }
        var escaped = declared.map(function (order) {
            return "<strong>" + escapeHtml(order) + "</strong>";
        }).join(", ");
        $notice.html(
            "La factura indica tener la orden de compra " + escaped +
            ". Revise si es correcta o seleccione la orden que corresponda."
        ).show();
    }

    function renderRefPoCandidates(orders) {
        var $body = $("#reference-po-body");
        $body.empty();
        var rows = orders || [];
        if (rows.length === 0) {
            $body.html('<tr><td colspan="7" class="text-center" style="color:#8a9099">Sin ordenes para los filtros</td></tr>');
            refreshRefPoCount();
            return;
        }
        rows.forEach(function (order) {
            var name = order.name || "";
            var checked = !!refPoSelected[name];
            var receipts = order.has_receipts
                ? (String(order.receipt_count || 0) + " (" + fmtMoney(order.unclaimed_total) + " libres)")
                : "Sin recepciones";
            var $tr = $("<tr class=\"ref-row ref-po-row\" data-order=\"" + escapeHtml(name) + "\">" +
                "<td class=\"text-center\"><input type=\"checkbox\" class=\"ref-po-check\" data-order=\"" + escapeHtml(name) + "\"" + (checked ? " checked" : "") + "></td>" +
                "<td>" + escapeHtml(name) + "</td>" +
                "<td>" + escapeHtml(order.transaction_date || "") + "</td>" +
                "<td>" + escapeHtml(order.oc_type || "") + "</td>" +
                "<td>" + escapeHtml(order.headquarter || "") + "</td>" +
                "<td>" + fmtMoney(order.grand_total) + "</td>" +
                "<td>" + escapeHtml(receipts) + "</td>" +
                "</tr>");
            if (checked) {
                $tr.addClass("selected");
            }
            $tr.on("click", function (event) {
                if ($(event.target).is("input")) {
                    return;
                }
                event.stopPropagation();
                toggleRefPo(name);
            });
            $body.append($tr);
        });
        refreshRefPoCount();
    }

    function refPoFilters() {
        var args = { doc_name: refPoDocName };
        var start = $("#reference-po-start").val();
        var end = $("#reference-po-end").val();
        var search = String($("#reference-po-search").val() || "").trim();
        if (start) {
            args.start = start;
        }
        if (end) {
            args.end = end;
        }
        if (search) {
            args.search = search;
        }
        return args;
    }

    function loadRefPoCandidates() {
        $("#reference-po-body").html(
            '<tr><td colspan="7" class="text-center" style="color:#8a9099">Cargando ordenes...</td></tr>'
        );
        refreshRefPoCount();

        petition_get_data(refPoFilters(),
            "qp_supplier_front.resources.documenteme.purchase_order_reference.get_purchase_order_candidates",
            function (response) {
                if (response.status !== 200) {
                    $("#reference-po-body").html(
                        '<tr><td colspan="7" class="text-center" style="color:#dc3545">' +
                        escapeHtml(response.msg || "Error") + "</td></tr>"
                    );
                    frappe.msgprint(response.msg || "Error al obtener ordenes");
                    return;
                }
                var data = response.data || {};
                window.__refPoOrders = data.orders || [];
                if (!refPoPreselected) {
                    preselectRefPo(data.manual_purchase_orders || []);
                    refPoPreselected = true;
                }
                renderRefPoDeclared(data.declared_purchase_orders || []);
                renderRefPoCandidates(window.__refPoOrders);
            }
        );
    }

    // Refresca solo la fila afectada (cabecera + detalle) sin recargar la lista.
    function refreshInvoiceRow(docName) {
        if (!docName) {
            window.filter_init();
            return;
        }
        petition_get_data({ doc_name: docName }, URL_RENDER_ROW, function (response) {
            if (!response || response.status !== 200 || !response.data) {
                window.filter_init();
                return;
            }
            var $current = $("tr.card-header").filter(function () {
                return $(this).attr("data-row") === docName;
            });
            if (!$current.length) {
                window.filter_init();
                return;
            }
            var target = $current.attr("data-target");
            var $detail = target ? $(target) : $();
            if (!$detail.length) {
                window.filter_init();
                return;
            }
            var wasOpen = $detail.hasClass("show");
            var $rows = $("<tbody>").html(response.data).children("tr");
            var $newHeader = $rows.filter(".card-header");
            var $newDetail = $rows.not(".card-header");
            if (!$newHeader.length || !$newDetail.length) {
                window.filter_init();
                return;
            }
            if (wasOpen) {
                $newHeader.attr("aria-expanded", "true");
                $newDetail.addClass("show");
            }
            $current.replaceWith($newHeader);
            $detail.replaceWith($newDetail);
        });
    }

    function submitRefPoAssign(approveFlag) {
        var selected = Object.keys(refPoSelected);
        if (!refPoDocName || selected.length === 0) {
            frappe.msgprint("Seleccione al menos una orden de compra");
            return;
        }
        var docName = refPoDocName;
        var overlayEl = document.getElementById("overlay");
        var savedOnClick = overlayEl ? overlayEl.onclick : null;
        if (overlayEl) {
            overlayEl.onclick = null;
            overlayEl.style.display = "block";
        }
        petition_get_data({
            doc_name: docName,
            purchase_orders: JSON.stringify(selected),
            approve: JSON.stringify(approveFlag)
        }, "qp_supplier_front.resources.documenteme.purchase_order_reference.assign_purchase_order",
            function (response) {
                if (overlayEl) {
                    overlayEl.onclick = savedOnClick;
                    overlayEl.style.display = "none";
                }
                if (response.status !== 200) {
                    frappe.msgprint(response.msg);
                    return;
                }
                var result = (response.data && response.data.result) || {};
                var processing = !!(result.enqueued > 0 || result.already_queued);
                $("#reference_po_modal").modal("hide");
                refreshInvoiceRow(docName);
                if (!processing) {
                    frappe.msgprint(response.msg);
                    return;
                }
                frappe.msgprint({
                    title: "Procesando",
                    message: "La factura se est\u00e1 procesando. Espere unos segundos."
                });
                setSyncProgress("Procesando factura...");
                pollBackgroundApproval(0, "Proceso finalizado.", function () {
                    refreshInvoiceRow(docName);
                }, "Procesando factura...");
            }
        );
    }

    var refPoSearchTimer = null;

    $(document).on("click", ".btn-control-purchase-order", function (event) {
        event.stopPropagation();
        refPoDocName = $(this).data("name");
        refPoSelected = {};
        refPoPreselected = false;
        $("#reference-po-start").val("");
        $("#reference-po-end").val("");
        $("#reference-po-search").val("");
        $("#reference-po-declared").hide().empty();
        $("#reference_po_modal").modal("show");
        loadRefPoCandidates();
    });

    $(document).on("change", ".ref-po-check", function (event) {
        event.stopPropagation();
        toggleRefPo($(this).attr("data-order"));
    });

    $("#reference-po-start, #reference-po-end").on("change", function () {
        loadRefPoCandidates();
    });

    $("#reference-po-search").on("input", function () {
        if (refPoSearchTimer) {
            clearTimeout(refPoSearchTimer);
        }
        refPoSearchTimer = setTimeout(loadRefPoCandidates, 400);
    });

    $("#reference-po-assign").on("click", function () {
        submitRefPoAssign(false);
    });

    // =====================================================================
    // Detalle completo (muchas OC / recepciones) en modal con pestanas.
    // La fila muestra solo un resumen y este modal trae el detalle completo
    // con el banco de recepciones seleccionable.
    // =====================================================================
    var invoiceDetailTab = "orders";

    function switchInvoiceDetailTab(tab) {
        invoiceDetailTab = tab === "receipts" ? "receipts" : "orders";
        $(".invoice-detail-tab").removeClass("active").each(function () {
            if ($(this).attr("data-tab") === invoiceDetailTab) {
                $(this).addClass("active");
            }
        });
        $(".invoice-detail-pane").each(function () {
            $(this).toggle($(this).attr("data-pane") === invoiceDetailTab);
        });
        filterInvoiceDetailPane();
    }

    function filterInvoiceDetailPane() {
        var query = String($("#invoice-detail-search").val() || "").trim().toLowerCase();
        var $pane = $('.invoice-detail-pane[data-pane="' + invoiceDetailTab + '"]');
        $pane.find(".oc-products-group, .receipt-item").each(function () {
            var haystack = String($(this).attr("data-search") || "");
            $(this).toggle(!query || haystack.indexOf(query) !== -1);
        });
    }

    function loadInvoiceDetail(docName, tab, invoiceNumber) {
        $("#invoice-detail-body").html(
            '<div style="color:#8a9099;font-size:13px;text-align:center;padding:24px">Cargando...</div>'
        );
        $("#invoice-detail-subtitle").text(
            invoiceNumber ? ("Factura " + invoiceNumber) : ""
        );
        $("#invoice-detail-search").val("");
        switchInvoiceDetailTab(tab);
        $("#invoice_detail_modal").modal("show");

        petition_get_data({ doc_name: docName, tab: tab || "orders" },
            "qp_supplier_front.resources.documenteme.invoice_detail.get_detail",
            function (response) {
                if (!response || response.status !== 200 || !response.data) {
                    $("#invoice-detail-body").html(
                        '<div style="color:#dc3545;font-size:13px;text-align:center;padding:24px">' +
                        escapeHtml((response && response.msg) || "No se pudo cargar el detalle") +
                        '</div>'
                    );
                    return;
                }
                $("#invoice-detail-body").html(response.data);
                switchInvoiceDetailTab(tab);
                initReceiptBanks();
            }
        );
    }

    $(document).on("click", ".btn-invoice-detail", function (event) {
        event.stopPropagation();
        loadInvoiceDetail(
            $(this).attr("data-name"),
            $(this).attr("data-tab"),
            $(this).attr("data-invoice")
        );
    });

    $(document).on("click", ".invoice-detail-tab", function (event) {
        event.preventDefault();
        switchInvoiceDetailTab($(this).attr("data-tab"));
    });

    $(document).on("input", "#invoice-detail-search", filterInvoiceDetailPane);

    $(document).on("hidden.bs.modal", "#invoice_detail_modal", function () {
        $("#invoice-detail-body").empty();
    });

    // =====================================================================
    // Discrepancia de precio factura vs orden de compra: al pasar el cursor
    // por el icono se resaltan los productos afectados en ambas tablas
    // (factura y orden de compra) que comparten el mismo grupo.
    // =====================================================================
    var PRICE_MISMATCH_HIGHLIGHT = "price-mismatch-highlight";

    $(document).on("mouseenter", ".price-mismatch-icon", function () {
        var group = $(this).attr("data-precio-grupo");
        if (group === undefined || group === null || group === "") {
            return;
        }
        var $scope = $(this).closest(".collapse");
        $scope.find('tr[data-precio-grupo="' + group + '"]')
            .addClass(PRICE_MISMATCH_HIGHLIGHT);
    });

    $(document).on("mouseleave", ".price-mismatch-icon", function () {
        var $scope = $(this).closest(".collapse");
        $scope.find("." + PRICE_MISMATCH_HIGHLIGHT)
            .removeClass(PRICE_MISMATCH_HIGHLIGHT);
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