// Entry point for the branded login page.
//
// This replaces the upstream theme's forked copy of frappe/www/login.py. We no
// longer shadow Frappe's login controller, so upstream security fixes to auth,
// rate limiting and redirect sanitization keep reaching this site. We only add
// presentational siblings around the form Frappe already rendered — the
// credential inputs themselves are never touched or re-created.

import { loginBrand } from "./core/login_brand.js";

loginBrand.mount();
