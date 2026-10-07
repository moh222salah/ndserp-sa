// NDS Restaurant Print Helpers (desk). QZ Tray support is guarded: without qz loaded it only shows a message.
frappe.provide("nds_restaurant.print");

nds_restaurant.print.print_via_qz = function (host, content) {
	if (typeof qz === "undefined") {
		frappe.msgprint(__("QZ Tray is not available"));
		return;
	}
	qz.websocket
		.connect({ host: host || "localhost" })
		.then(function () {
			return qz.printers.getDefault();
		})
		.then(function (printer) {
			const config = qz.configs.create(printer);
			return qz.print(config, [{ type: "html", format: "plain", data: content }]);
		})
		.catch(function (err) {
			console.error(err);
			frappe.msgprint(__("QZ print failed: {0}", [err]));
		});
};
