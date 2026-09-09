$(document).ready(function () {
	const $orderSelect = $("#purchase_order_select");
	const $totalValue = $("#order_total_value");
	const $availableValue = $("#available_value");
	const $amountToInvoice = $("#amount_to_invoice");
	const $submitButton = $("#submit_collection_account");

	document.getElementById("docs").addEventListener("change", function () {
		const status = document.getElementById("status-docs");
		status.textContent = this.files.length ? this.files[0].name : "Archivo no cargado";
	});

	function formatCurrency(value, currency) {
		const numericValue = Number(value || 0);

		return new Intl.NumberFormat("es-CO", {
			style: "currency",
			currency: currency || "COP",
			minimumFractionDigits: 0,
			maximumFractionDigits: 2,
		}).format(numericValue);
	}

	function maskCurrency(value) {
		const numericValue = Number(value || 0);
		const cents = Math.round(numericValue * 100);
		return formatColombianCurrency(String(cents));
	}

	function parseCurrency(value) {
		const cleaned = String(value || "").replace(/\./g, "").replace(",", ".");
		const num = parseFloat(cleaned);
		return isNaN(num) ? 0 : num;
	}

	function updateOrderValues() {
		const $selectedOption = $orderSelect.find(":selected");

		if (!$selectedOption.length || !$selectedOption.val()) {
			$totalValue.val("");
			$availableValue.val("");
			$amountToInvoice.val("");
			return;
		}

		const totalValue = $selectedOption.data("total-value");
		const availableValue = $selectedOption.data("available-value");
		const currency = $selectedOption.data("currency");

		$totalValue.val(formatCurrency(totalValue, currency));
		$availableValue.val(formatCurrency(availableValue, currency));
		$amountToInvoice.val(maskCurrency(availableValue));
	}

	$orderSelect.on("change", updateOrderValues);

	function showServerError(r) {
		let message = "Error al crear la cuenta de cobro.";
		try {
			if (r && r._server_messages) {
				const raw = JSON.parse(r._server_messages);
				if (raw && raw.length && JSON.parse(raw[0]).message) {
					message = JSON.parse(raw[0]).message;
				}
			} else if (r && r.message && r.message.msg) {
				message = r.message.msg;
			}
		} catch (e) {
			// mantiene el mensaje por defecto
		}
		frappe.msgprint(message);
	}

	$submitButton.on("click", function () {
		const orderName = $orderSelect.val();
		const amount = parseCurrency($amountToInvoice.val());

		if (!orderName) {
			frappe.msgprint("Selecciona una orden.");
			return;
		}
		if (amount <= 0) {
			frappe.msgprint("El monto a facturar debe ser mayor a cero.");
			return;
		}

		async function uploadDocs(file) {
			if (!file) {
				return null;
			}

			const formData = new FormData();
			formData.append('file', file);

			try {
				const response = await fetch('/api/method/upload_file', {
					method: 'POST',
					body: formData,
					headers: {
						'X-Frappe-CSRF-Token': frappe.csrf_token,
					},
				});

				if (!response.ok) {
					throw new Error('Error al subir el archivo');
				}

				const data = await response.json();
				return data.message.file_url;
			} catch (error) {
				console.error('Error al subir el archivo:', error);
				frappe.msgprint("Error al subir el archivo.");
				return null;
			}
		}

		uploadDocs($("#docs")[0].files[0]).then((fileUrl) => {
			frappe.call({
				method: "qp_supplier_front.resources.collection_accounts.collection_accounts.create_collection_account",
				args: {
					purchase_order: orderName,
					amount_to_invoice: amount,
					observations: $("#observations").val(),
					docs: fileUrl,
				},
				callback: function (r) {
					if (r && r.exc) {
						showServerError(r);
						return;
					}
					frappe.msgprint({
						title: __("Éxito"),
						message: __("La cuenta de cobro fue creada con éxito"),
						indicator: "green",
					});

					frappe.msg_dialog.$wrapper.on("hidden.bs.modal", function () {
						window.location.href = "/documenteme/collection_accounts";
					});
				},
			});
		});
	});

	updateOrderValues();
});