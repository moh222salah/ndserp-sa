// =====================================================================
// LOGIN BRAND v3 — modern split-screen, bilingual, no-scroll, animated
// =====================================================================
// Reference: white card on form side (LEFT/RIGHT — configurable), dark
// gradient brand panel on the other side with company info + animated
// orbiting brand icons.
//
// SAFE: only injects siblings/wrappers around Frappe's login form. We
// never modify the form's auth-bearing inputs. Each text field has an
// Arabic and English value; the current page language picks the right
// one automatically.
// =====================================================================

const ICONS = {
	mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>',
	phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.37 1.9.72 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.35 1.85.59 2.81.72a2 2 0 0 1 1.72 2.01z"/></svg>',
	pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
	globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/></svg>',
	quote: '<svg viewBox="0 0 24 24" fill="currentColor" width="40" height="40" opacity="0.18"><path d="M9.4 7c-3 1.5-4.4 4.6-4.4 7.4 0 2.4 1.6 4 3.6 4 1.7 0 3-1.3 3-3 0-1.6-1.1-2.8-2.6-2.8-.4 0-.7 0-.9.1.2-1.7 1.5-3.5 3.3-4.4L9.4 7zm9 0c-3 1.5-4.4 4.6-4.4 7.4 0 2.4 1.6 4 3.6 4 1.7 0 3-1.3 3-3 0-1.6-1.1-2.8-2.6-2.8-.4 0-.7 0-.9.1.2-1.7 1.5-3.5 3.3-4.4L18.4 7z"/></svg>',
	fb: '<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M22 12a10 10 0 1 0-11.56 9.88V14.9H7.9V12h2.54V9.8c0-2.51 1.49-3.9 3.78-3.9 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.62.77-1.62 1.56V12h2.76l-.44 2.9h-2.32v6.98A10 10 0 0 0 22 12z"/></svg>',
	tw: '<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M18.244 2H21l-6.52 7.45L22 22h-6.83l-4.78-6.27L4.8 22H2.04l6.97-7.96L2 2h6.99l4.32 5.7L18.24 2zm-2.4 18h1.55L7.27 4H5.6l10.24 16z"/></svg>',
	li: '<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9h4v12H3V9zm7 0h3.84v1.64h.05c.53-1 1.84-2.05 3.79-2.05 4.05 0 4.8 2.67 4.8 6.14V21h-4v-5.4c0-1.29-.02-2.94-1.79-2.94-1.8 0-2.07 1.4-2.07 2.85V21h-4V9z"/></svg>',
	ig: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>',
	// orbiting decorative icons in the brand panel background
	gear: '<svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28"><path d="M19.43 12.98c.04-.32.07-.65.07-.98s-.03-.66-.07-.98l2.11-1.65a.5.5 0 0 0 .12-.64l-2-3.46a.5.5 0 0 0-.61-.22l-2.49 1a7.03 7.03 0 0 0-1.7-.98l-.38-2.65A.5.5 0 0 0 14 2h-4a.5.5 0 0 0-.5.42l-.38 2.65c-.62.24-1.18.57-1.7.98l-2.49-1a.5.5 0 0 0-.61.22l-2 3.46a.5.5 0 0 0 .12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98L2.44 14.63a.5.5 0 0 0-.12.64l2 3.46a.5.5 0 0 0 .61.22l2.49-1c.52.41 1.08.74 1.7.98l.38 2.65a.5.5 0 0 0 .5.42h4a.5.5 0 0 0 .5-.42l.38-2.65c.62-.24 1.18-.57 1.7-.98l2.49 1a.5.5 0 0 0 .61-.22l2-3.46a.5.5 0 0 0-.12-.64l-2.11-1.65zM12 15.5A3.5 3.5 0 1 1 15.5 12 3.5 3.5 0 0 1 12 15.5z"/></svg>',
	chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="28" height="28"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 16l3-4 4 3 4-7"/></svg>',
	check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="28" height="28"><polyline points="20 6 9 17 4 12"/></svg>',
	user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="28" height="28"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
	cube: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="28" height="28"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96L12 12l8.73-5.04M12 22V12"/></svg>',
};

function esc(s) {
	return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
		"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
	}[c]));
}

function safeUrl(u) {
	if (!u) return "";
	u = String(u);
	if (/^(https?:)?\/\//i.test(u) || u.startsWith("/")) return u;
	return "https://" + u;
}

function isLoginPage() {
	const p = location.pathname || "";
	if (p === "/login" || p.startsWith("/login/")) return true;
	if (p === "/login-with-email-link") return true;
	return !!document.querySelector(".for-login, #login-with-email-login, .login-content");
}

function curLang() {
	const html = document.documentElement;
	if (html.getAttribute("lang") === "ar" || html.getAttribute("dir") === "rtl") return "ar";
	return "en";
}

// Pick the language-appropriate text: ar → falls back to English if Arabic empty
function pick(s, ar_key, en_key) {
	const lang = curLang();
	if (lang === "ar") return s[ar_key] || s[en_key] || "";
	return s[en_key] || s[ar_key] || "";
}

/** Drop the pre-paint guard set in <head> by website.py. Safe to call twice. */
function release() {
	document.documentElement.classList.remove("amt-lb-pending");
}


const LANGUAGE_OPTIONS = [
        { code: "ar", label: "العربية" },
        { code: "en", label: "English" },
];

function setPreferredLanguage(lang) {
        const code = lang === "en" ? "en" : "ar";

        document.cookie =
                `preferred_language=${encodeURIComponent(code)}; Max-Age=2592000; Path=/; SameSite=Lax` +
                (window.location.protocol === "https:" ? "; Secure" : "");

        const url = new URL(window.location.href);
        url.searchParams.set("_lang", code);

        window.location.assign(
                url.pathname + url.search + url.hash
        );
}

function mountLanguageControl(card) {
  const existing = card.querySelector(".amt-lb-language");
  if (existing) existing.remove();

  const button = document.createElement("button");
  button.type = "button";
  button.className = "amt-lb-language";
  button.setAttribute("aria-label", curLang() === "ar" ? "التبديل إلى الإنجليزية" : "Switch to Arabic");
  button.setAttribute("title", curLang() === "ar" ? "التبديل إلى الإنجليزية" : "Switch to Arabic");
  button.innerHTML = `<span class="amt-lb-language-icon" aria-hidden="true">${ICONS.globe}</span>`;

  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();

    const nextLanguage = curLang() === "ar" ? "en" : "ar";
    setPreferredLanguage(nextLanguage);
  });

  card.appendChild(button);
  return button;
}

function applyArabicLoginPresentation(card) {
        const root =
                document.querySelector(".for-login.amt-lb-on") ||
                document.querySelector(".for-login") ||
                card;

        if (!root) return;

        const detectArabic = () => {
                const queryLang =
                        new URLSearchParams(window.location.search).get("_lang");

                const bootLang =
                        window.frappe &&
                        window.frappe.boot &&
                        window.frappe.boot.lang;

                const htmlLang = (
                        document.documentElement.getAttribute("lang") || ""
                ).toLowerCase();

                return (
                        queryLang === "ar" ||
                        String(bootLang || "").toLowerCase() === "ar" ||
                        htmlLang === "ar" ||
                        htmlLang.startsWith("ar-") ||
                        curLang() === "ar"
                );
        };

        const sync = () => {
                const isArabic = detectArabic();
                const direction = isArabic ? "rtl" : "ltr";
                const align = isArabic ? "right" : "left";

                const setPresentation = (element, textAlign = align) => {
                        if (!element) return;

                        element.setAttribute("dir", direction);
                        element.style.setProperty("direction", direction);
                        element.style.setProperty("text-align", textAlign);
                };

                document.documentElement.setAttribute("dir", direction);
                document.documentElement.style.setProperty(
                        "direction",
                        direction
                );

                if (document.body) {
                        document.body.setAttribute("dir", direction);
                        document.body.style.setProperty(
                                "direction",
                                direction
                        );
                }

                setPresentation(root);
                setPresentation(
                        root.querySelector(".amt-lb-split")
                );
                setPresentation(
                        root.querySelector(".amt-lb-form-side")
                );

                const scope =
                        root.querySelector(".amt-lb-card") ||
                        root;

                setPresentation(scope);

                const content =
                        scope.querySelector(".login-content") ||
                        scope;

                setPresentation(content);
                setPresentation(
                        content.querySelector("form")
                );

                content.querySelectorAll(
                        ".form-group, .frappe-control, .form-column, " +
                        ".control-input-wrapper, .input-with-feedback, " +
                        ".input-group, label, .control-label, " +
                        ".forgot-password-message"
                ).forEach((element) => {
                        setPresentation(element);

                        if (
                                element.matches(
                                        "label, .control-label, .form-group, " +
                                        ".frappe-control, .form-column, " +
                                        ".forgot-password-message"
                                )
                        ) {
                                element.style.setProperty(
                                        "text-align",
                                        align
                                );
                        }
                });

                content.querySelectorAll(
                        "input, textarea, select, .form-control"
                ).forEach((element) => {
                        setPresentation(element, align);

                        element.style.setProperty(
                                "writing-mode",
                                "horizontal-tb"
                        );

                        element.style.setProperty(
                                "unicode-bidi",
                                "plaintext"
                        );
                });

                content.querySelectorAll(
                        "input::placeholder, textarea::placeholder"
                );

                content.querySelectorAll(
                        "a[href='#forgot'], a[href*='#forgot'], " +
                        ".forgot-password-message a"
                ).forEach((link) => {
                        const wanted = isArabic
                                ? "نسيت كلمة المرور؟"
                                : "Forgot password?";

                        if (link.textContent.trim() !== wanted) {
                                link.textContent = wanted;
                        }

                        setPresentation(link, align);
                        link.style.setProperty(
                                "white-space",
                                "normal"
                        );
                });

                content.querySelectorAll(
                        "button[type='submit'], .btn-login, .btn-primary"
                ).forEach((button) => {
                        setPresentation(button, "center");
                });
        };

        sync();

        if (!window.__vaLoginArabicRuntimeObserver) {
                const observer = new MutationObserver(() => {
                        sync();
                });

                const observeTarget =
                        document.body ||
                        document.documentElement;

                if (observeTarget) {
                        observer.observe(observeTarget, {
                                subtree: true,
                                childList: true,
                                characterData: true,
                        });

                        window.__vaLoginArabicRuntimeObserver = observer;
                }
        }

        if (!window.__vaLoginArabicRuntimeTimers) {
                window.__vaLoginArabicRuntimeTimers = true;

                if (typeof requestAnimationFrame === "function") {
                        requestAnimationFrame(sync);
                        requestAnimationFrame(() => {
                                requestAnimationFrame(sync);
                        });
                }

                window.setTimeout(sync, 0);
                window.setTimeout(sync, 100);
                window.setTimeout(sync, 300);
                window.setTimeout(sync, 700);
                window.setTimeout(sync, 1200);
                window.setTimeout(sync, 2000);
        }
}

async function fetchSettings() {
	// Preferred path: website.py inlined the settings into <head>, so the page
	// can be decorated in the same tick the bundle runs — no round trip, and
	// nothing to wait for. The fetch below is the fallback for a page served
	// before that hook existed (stale cache, another app's base template).
	if (window.__amtLoginSettings) return window.__amtLoginSettings;

	try {
		const res = await fetch(
			"/api/method/amir_theme_v16.amir_theme.doctype.login_page_settings.login_page_settings.get_public_settings",
			{ headers: { Accept: "application/json" }, credentials: "same-origin" }
		);
		if (!res.ok) return null;
		const j = await res.json();
		return j && j.message ? j.message : null;
	} catch (e) {
		return null;
	}
}

function buildBrandPanel(s) {
	const accent = s.accent_color || "#0f766e";
	const bg = s.background_image || "";

	const company = pick(s, "company_name_ar", "company_name");
	const tagline = pick(s, "tagline_ar", "tagline");
	const desc    = pick(s, "description_ar", "description");
	const addr    = pick(s, "address_ar", "address");

	const items = [];
	if (addr)      items.push(`<div class="amt-lb-contact"><span class="amt-lb-icn">${ICONS.pin}</span><span>${esc(addr)}</span></div>`);
	if (s.phone)   items.push(`<a class="amt-lb-contact" href="tel:${esc(s.phone)}"><span class="amt-lb-icn">${ICONS.phone}</span><span dir="ltr">${esc(s.phone)}</span></a>`);
	if (s.email)   items.push(`<a class="amt-lb-contact" href="mailto:${esc(s.email)}"><span class="amt-lb-icn">${ICONS.mail}</span><span dir="ltr">${esc(s.email)}</span></a>`);
	if (s.website) items.push(`<a class="amt-lb-contact" href="${esc(safeUrl(s.website))}" target="_blank" rel="noopener"><span class="amt-lb-icn">${ICONS.globe}</span><span dir="ltr">${esc(s.website)}</span></a>`);

	let social = "";
	if (s.show_social) {
		const socials = [];
		if (s.facebook_url)  socials.push(`<a href="${esc(safeUrl(s.facebook_url))}"  target="_blank" rel="noopener" aria-label="Facebook">${ICONS.fb}</a>`);
		if (s.twitter_url)   socials.push(`<a href="${esc(safeUrl(s.twitter_url))}"   target="_blank" rel="noopener" aria-label="Twitter">${ICONS.tw}</a>`);
		if (s.linkedin_url)  socials.push(`<a href="${esc(safeUrl(s.linkedin_url))}"  target="_blank" rel="noopener" aria-label="LinkedIn">${ICONS.li}</a>`);
		if (s.instagram_url) socials.push(`<a href="${esc(safeUrl(s.instagram_url))}" target="_blank" rel="noopener" aria-label="Instagram">${ICONS.ig}</a>`);
		if (socials.length) social = `<div class="amt-lb-social">${socials.join("")}</div>`;
	}

	// orbiting decorative icons across the brand panel
	const orbits = `
		<div class="amt-lb-orbit amt-lb-orbit--1"><span style="--d:0s">${ICONS.gear}</span><span style="--d:-3s">${ICONS.chart}</span><span style="--d:-6s">${ICONS.check}</span><span style="--d:-9s">${ICONS.cube}</span></div>
		<div class="amt-lb-orbit amt-lb-orbit--2"><span style="--d:0s">${ICONS.user}</span><span style="--d:-4s">${ICONS.globe}</span><span style="--d:-8s">${ICONS.mail}</span></div>
	`;

	const panel = document.createElement("aside");
	panel.className = "amt-lb-panel";
	panel.style.setProperty("--amt-lb-accent", accent);
	if (bg) panel.style.setProperty("--amt-lb-bg", `url('${bg.replace(/'/g, "%27")}')`);
	panel.innerHTML = `
		<div class="amt-lb-crystal" aria-hidden="true">
			<i class="amt-lb-facet amt-lb-facet--1"></i>
			<i class="amt-lb-facet amt-lb-facet--2"></i>
			<i class="amt-lb-facet amt-lb-facet--3"></i>
			<i class="amt-lb-facet amt-lb-facet--4"></i>
			<i class="amt-lb-facet amt-lb-facet--5"></i>
			<span class="amt-lb-sheen"></span>
		</div>
		<div class="amt-lb-content">
			<div class="amt-lb-quote">${ICONS.quote}</div>
			${company ? `<h1 class="amt-lb-title">${esc(company)}</h1>` : ""}
			${tagline ? `<p class="amt-lb-tagline">${esc(tagline)}</p>` : ""}
			${desc ? `<p class="amt-lb-desc">${esc(desc).replace(/\n/g, "<br>")}</p>` : ""}
			${items.length ? `<div class="amt-lb-contacts">${items.join("")}</div>` : ""}
			${social}
		</div>
	`;
	return panel;
}

let injected = false;
async function decorate() {
	if (injected) return;
	if (!isLoginPage()) return;
	const settings = await fetchSettings();
	// Nothing to brand — show Frappe's own card rather than leaving it hidden.
	if (!settings || !settings.enabled) return release();

	const content =
		document.querySelector(".login-content") ||
		document.querySelector(".page-card-container") ||
		document.querySelector(".for-login")?.parentElement;
	if (!content) return release();

	if (document.querySelector(".amt-lb-panel")) { injected = true; return release(); }

	// hide Frappe's default page chrome — our card replaces the page title
	document.querySelectorAll(".navbar, .login-headline, .login-content > h4, header.navbar, .page-card-head")
		.forEach((el) => { el.style.display = "none"; });

	const wrap = document.createElement("div");
	wrap.className = "amt-lb-split";
	const brandFirst = settings.panel_position === "left" || curLang() === "ar";
	if (brandFirst) wrap.classList.add("amt-lb-split--brand-left");

	// FORM SIDE with explicit white CARD wrapper — guarantees the visual.
	const formSide = document.createElement("div");
	formSide.className = "amt-lb-form-side";
	const card = document.createElement("div");
	card.className = "amt-lb-card";

	// Logo + Welcome header INSIDE the card
	const head = document.createElement("div");
	head.className = "amt-lb-form-head";
	const welcomeAr = "أهلاً بعودتك!";
	const welcomeEn = "Welcome Back!";
	const subAr = "سجّل دخولك للوصول إلى لوحة التحكم";
	const subEn = "Sign in to access your dashboard";
	// Logo block — show the real logo if provided, otherwise a stylised
	// monogram (first letter of the company name OR a bracket icon) so the
	// card always looks complete like the reference design.
	const companyDisplay = pick(settings, "company_name_ar", "company_name");
	const monogram = companyDisplay
		? companyDisplay.trim().charAt(0).toUpperCase()
		: "{ }";
	// Logo resolution, in order of preference:
	//   1. the customer's own upload (Login Page Settings -> logo)
	//   2. the shipped default ERP mark
	// The monogram fallback is gone: a single letter in a coloured square was a
	// placeholder, not a brand. The default mark is masked rather than placed in
	// an <img> so it inherits currentColor and therefore works on the dark panel
	// and the white card from one file.
	const logoHtml = settings.logo
		? `<div class="amt-lb-form-logo-wrap amt-lb-form-logo-wrap--custom"><img class="amt-lb-form-logo" src="${esc(settings.logo)}" alt=""/></div>`
		: `<div class="amt-lb-form-logo-wrap amt-lb-form-logo-wrap--default" role="img" aria-label="ERP"></div>`;
	const brandLabel = companyDisplay ? esc(companyDisplay) : "";
	head.innerHTML = `
		<div class="amt-lb-form-brand">
			${logoHtml}
			${brandLabel ? `<span class="amt-lb-form-brand-name">${brandLabel}</span>` : ""}
		</div>
		<h2 class="amt-lb-form-title">${curLang() === "ar" ? welcomeAr : welcomeEn}</h2>
		<p class="amt-lb-form-sub">${curLang() === "ar" ? subAr : subEn}</p>
	`;
	card.appendChild(head);
        mountLanguageControl(card);

        applyArabicLoginPresentation(card);
	// Move ALL of Frappe's login form children into the card (NOT formSide
	// directly) — guarantees they're inside our white card.
	while (content.firstChild) card.appendChild(content.firstChild);
	formSide.appendChild(card);

	const brand = buildBrandPanel(settings);
	if (brandFirst) {
		wrap.appendChild(brand);
		wrap.appendChild(formSide);
	} else {
		wrap.appendChild(formSide);
		wrap.appendChild(brand);
	}
	content.appendChild(wrap);

	document.documentElement.classList.add("amt-lb-on");
	if (settings.accent_color) {
		document.documentElement.style.setProperty("--amt-lb-accent-global", settings.accent_color);
	}
	injected = true;
	release();
}

function createStableLanguageControl(card) {
  const existing = card.querySelector(".amt-lb-language");
  if (existing) existing.remove();

  const button = document.createElement("button");
  button.type = "button";
  button.className = "amt-lb-language";
  button.setAttribute("aria-label", curLang() === "ar" ? "التبديل إلى الإنجليزية" : "Switch to Arabic");
  button.setAttribute("title", curLang() === "ar" ? "التبديل إلى الإنجليزية" : "Switch to Arabic");
  button.innerHTML = `<span class="amt-lb-language-icon" aria-hidden="true">${ICONS.globe}</span>`;

  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();

    const nextLanguage = curLang() === "ar" ? "en" : "ar";
    setPreferredLanguage(nextLanguage);
  });

  card.appendChild(button);
  return button;
}

function stableFallbackBrand(settings) {
        const company = pick(
                settings || {},
                "company_name_ar",
                "company_name"
        ) || "";

        const panel = document.createElement("aside");
        panel.className = "amt-lb-panel";

        if (settings && settings.accent_color) {
                panel.style.setProperty("--amt-lb-accent", settings.accent_color);
        }

        if (settings && settings.background_image) {
                panel.style.setProperty(
                        "--amt-lb-bg",
                        `url('${String(settings.background_image).replace(/'/g, "%27")}')`
                );
        }

        panel.innerHTML = `
                <div class="amt-lb-crystal" aria-hidden="true">
                        <i class="amt-lb-facet amt-lb-facet--1"></i>
                        <i class="amt-lb-facet amt-lb-facet--2"></i>
                        <i class="amt-lb-facet amt-lb-facet--3"></i>
                        <i class="amt-lb-facet amt-lb-facet--4"></i>
                        <i class="amt-lb-facet amt-lb-facet--5"></i>
                        <span class="amt-lb-sheen"></span>
                </div>

                <div class="amt-lb-content">
                        <div class="amt-lb-quote">${ICONS.quote}</div>
                        <h1 class="amt-lb-title">${esc(company)}</h1>
                        <p class="amt-lb-tagline">
                                ${curLang() === "ar"
                                        ? "نظام متكامل لإدارة أعمالك"
                                        : "Integrated business management system"}
                        </p>
                        <p class="amt-lb-desc">
                                ${curLang() === "ar"
                                        ? "حلول أعمال حديثة تمنحك رؤية أوضح وتحكمًا أفضل."
                                        : "Modern business tools for clearer visibility and better control."}
                        </p>
                </div>
        `;

        return panel;
}

function stableMountLogin() {
        if (!isLoginPage()) return;

        const root = document.querySelector("section.for-login");
        const content = root && root.querySelector(".login-content");

        if (!root || !content) {
                release();
                return;
        }

        if (document.querySelector(".amt-lb-split")) {
                document.documentElement.classList.add("amt-lb-on");
                release();
                return;
        }

        const settings =
                window.__amtLoginSettings && window.__amtLoginSettings.enabled
                        ? window.__amtLoginSettings
                        : {
                                enabled: 1,
                                company_name: "",
                                company_name_ar: "",
                                panel_position: "right",
                                accent_color: "#14477E",
                        };

        document.querySelectorAll(
                ".navbar, .login-headline, .login-content > h4, header.navbar, .page-card-head"
        ).forEach((el) => {
                el.style.display = "none";
        });

        const split = document.createElement("div");
        split.className = "amt-lb-split";

        const brandFirst =
                settings.panel_position === "left" || curLang() === "ar";

        if (brandFirst) {
                split.classList.add("amt-lb-split--brand-left");
        }

        const formSide = document.createElement("div");
        formSide.className = "amt-lb-form-side";

        const card = document.createElement("div");
        card.className = "amt-lb-card";

        const head = document.createElement("div");
        head.className = "amt-lb-form-head";

        const companyDisplay =
                pick(settings, "company_name_ar", "company_name") || "";

        const logoHtml = settings.logo
                ? `<div class="amt-lb-form-logo-wrap amt-lb-form-logo-wrap--custom">
                        <img class="amt-lb-form-logo" src="${esc(settings.logo)}" alt=""/>
                   </div>`
                : `<div class="amt-lb-form-logo-wrap amt-lb-form-logo-wrap--default"
                        role="img"
                        aria-label="ERP"></div>`;

        head.innerHTML = `
                <div class="amt-lb-form-brand">
                        ${logoHtml}
                        <span class="amt-lb-form-brand-name">${esc(companyDisplay)}</span>
                </div>

                <h2 class="amt-lb-form-title">
                        ${curLang() === "ar" ? "أهلاً بعودتك!" : "Welcome Back!"}
                </h2>

                <p class="amt-lb-form-sub">
                        ${curLang() === "ar"
                                ? "سجّل دخولك للوصول إلى لوحة التحكم"
                                : "Sign in to access your dashboard"}
                </p>
        `;

        card.appendChild(head);
        createStableLanguageControl(card);

        applyArabicLoginPresentation(card);
        /*
         * Preserve the complete Frappe login-content node and therefore every
         * auth-bearing field, form class and existing event contract.
         */
        card.appendChild(content);
        formSide.appendChild(card);

        let brand;

        try {
                brand = buildBrandPanel(settings);
        } catch (error) {
                console.error("[VA Login] buildBrandPanel failed; using stable fallback.", error);
                brand = stableFallbackBrand(settings);
        }

        if (brandFirst) {
                split.appendChild(brand);
                split.appendChild(formSide);
        } else {
                split.appendChild(formSide);
                split.appendChild(brand);
        }

        root.appendChild(split);

        document.documentElement.classList.add("amt-lb-on");

        if (settings.accent_color) {
                document.documentElement.style.setProperty(
                        "--amt-lb-accent-global",
                        settings.accent_color
                );
        }

        injected = true;
        release();
}

export const loginBrand = {
        mount() {
                const run = () => {
                        try {
                                stableMountLogin();
                        } catch (error) {
                                console.error("[VA Login] stable mount failed:", error);
                                release();
                        }
                };

                if (document.readyState === "loading") {
                        document.addEventListener("DOMContentLoaded", run, { once: true });
                } else {
                        run();
                }

                setTimeout(run, 300);
                setTimeout(run, 900);
                setTimeout(run, 1800);
        },
};

loginBrand.mount();
