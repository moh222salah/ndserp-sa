/**
 * Language switcher for the Frappe desk.
 *
 * Adds an Arabic/English toggle to the navbar. Writes the choice to
 * `User.language` and reloads so the whole desk (including RTL) follows.
 *
 * Replaces an earlier version that polled with a 1s setInterval forever and
 * overwrote the global `document.onclick` handler.
 */

const LANGUAGES = [
	{ code: "ar", label: "العربية" },
	{ code: "en", label: "English" },
];

const CONTAINER_ID = "ndserp-lang-switcher";

function build_switcher() {
	if (document.getElementById(CONTAINER_ID)) return;

	// amir_theme_v16 owns the language switcher when it is installed: it renders
	// one into v16's real top bar (`.page-head`) and lets the site choose the
	// placement via "Amir Theme Settings". Standing down here keeps there from
	// ever being two switchers on screen. Detected by the theme's own boot
	// payload rather than by asset name, so this stays correct regardless of
	// which placement the theme is configured for.
	if (window.frappe?.boot?.amt_settings) return;

	// Drop into the navbar's utility area so it moves with the layout and
	// flips correctly in RTL, instead of being pinned to fixed coordinates.
	//
	// NOTE: Frappe v16's desk has no Bootstrap `.navbar` at all - the top bar is
	// `.page-head` - so on v16 this selector never matches and the switcher is
	// inert. It is kept for v15-era sites; on v16 the theme above provides it.
	const navbar = document.querySelector(".navbar .navbar-nav, .navbar-collapse .navbar-nav");
	if (!navbar) return;

	const current = (frappe.boot.lang || "en").slice(0, 2);

	const item = document.createElement("li");
	item.id = CONTAINER_ID;
	item.className = "nav-item dropdown ndserp-lang-switcher";

	const toggle = document.createElement("a");
	toggle.className = "nav-link";
	toggle.href = "#";
	toggle.setAttribute("role", "button");
	toggle.setAttribute("aria-haspopup", "true");
	toggle.setAttribute("aria-expanded", "false");
	toggle.setAttribute("aria-label", __("Change language"));
	toggle.textContent = current === "ar" ? "ع" : "EN";

	const menu = document.createElement("div");
	menu.className = "dropdown-menu dropdown-menu-right";

	LANGUAGES.forEach((lang) => {
		const option = document.createElement("button");
		option.type = "button";
		option.className = "dropdown-item";
		option.textContent = lang.label;
		option.disabled = lang.code === current;
		option.addEventListener("click", (event) => {
			event.preventDefault();
			set_language(lang.code, option);
		});
		menu.appendChild(option);
	});

	toggle.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopPropagation();
		const open = menu.classList.toggle("show");
		toggle.setAttribute("aria-expanded", String(open));
	});

	// Additive listener - does not clobber other click handlers on the page.
	document.addEventListener("click", (event) => {
		if (!item.contains(event.target)) {
			menu.classList.remove("show");
			toggle.setAttribute("aria-expanded", "false");
		}
	});

	item.appendChild(toggle);
	item.appendChild(menu);
	navbar.appendChild(item);
}

function set_language(code, option) {
	const previous = option.textContent;
	option.textContent = __("Saving...");
	option.disabled = true;

	frappe.db
		.set_value("User", frappe.session.user, "language", code)
		.then(() => {
			window.location.reload();
		})
		.catch((error) => {
			option.textContent = previous;
			option.disabled = false;
			frappe.msgprint({
				title: __("Could not change language"),
				message: error && error.message ? error.message : __("Please try again."),
				indicator: "red",
			});
		});
}

// `app_ready` fires once the desk is booted; `toolbar_setup` fires after the
// navbar is rendered. Listening to both covers a full load and a soft route.
$(document).on("app_ready toolbar_setup", () => {
	if (frappe.session.user !== "Guest") {
		build_switcher();
	}
});
