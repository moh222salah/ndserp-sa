frappe.ui.form.on("Mock PTS Controller", {
	refresh(frm) {
		if (frm.is_new()) return;
		const call = (method, msg) => frm.call(method).then((r) => {
			frappe.show_alert({ message: r.message || msg, indicator: "green" });
			frm.reload_doc();
		});

		if (frm.doc.is_running) {
			frm.add_custom_button(__("Stop Simulator"), () => call("stop", "Stopped"));
		} else {
			frm.add_custom_button(__("Start Simulator"), () => call("start", "Started"))
				.addClass("btn-primary");
		}

		const g = __("Generate");
		frm.add_custom_button(__("Transaction"), () => call("generate_transaction"), g);
		frm.add_custom_button(__("Tank Measurement"), () => call("generate_measurement"), g);
		frm.add_custom_button(__("Alert"), () => call("generate_alert"), g);
		frm.add_custom_button(__("Delivery"), () => call("generate_delivery"), g);

		const c = __("Connection");
		frm.add_custom_button(__("Simulate Loss"), () => call("simulate_connection_loss"), c);
		frm.add_custom_button(__("Restore"), () => call("restore_connection"), c);

		frm.add_custom_button(__("Open Dashboard"), () =>
			frappe.set_route("gas_station_dashboard"));
	},
});
