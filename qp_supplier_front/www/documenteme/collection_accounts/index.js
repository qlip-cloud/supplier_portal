$(document).ready(function () {
	const $orderSelect = $("#purchase_order_select");
	const $totalValue = $("#order_total_value");
	const $availableValue = $("#available_value");
	const $amountToInvoice = $("#amount_to_invoice");
	const $submitButton = $("#submit_collection_account");

	function formatCurrency(value, currency) {
		const numericValue = Number(value || 0);

		return new Intl.NumberFormat("es-CO", {
			style: "currency",
			currency: currency || "COP",
			minimumFractionDigits: 0,
			maximumFractionDigits: 2,
		}).format(numericValue);
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
		$amountToInvoice.val(Number(availableValue || 0));
	}

	$orderSelect.on("change", updateOrderValues);

	$submitButton.on("click", function () {
		const orderName = $orderSelect.val();
		const amount = Number($amountToInvoice.val() || 0);

		if (!orderName) {
			frappe.msgprint("Selecciona una orden.");
			return;
		}
		if (amount <= 0) {
			frappe.msgprint("El monto a facturar debe ser mayor a cero.");
			return;
		}

		// Ajusta el método whitelisted según tu backend
		frappe.call({
			method: "qp_supplier_front.api.create_collection_account",
			args: {
				purchase_order: orderName,
				amount_to_invoice: amount,
			},
			callback: function (r) {
				if (!r.exc) {
					window.location.href = "/collection_accounts";
				}
			},
		});
	});

	updateOrderValues();
});