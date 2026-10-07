# NDS ERP (`ndserp`)

Arabic-first localisation layer for [ERPNext](https://github.com/frappe/erpnext) v15.

The app does not add new doctypes. It is a **customisation carrier**: it packages
the Arabic workspaces, the desk language switcher and the shared Customize Form
changes so that the same setup can be reproduced on any site with
`bench install-app ndserp` instead of being re-done by hand.

> **طبقة تعريب لـ ERPNext.** التطبيق لا يضيف Doctypes جديدة، بل يحمل التخصيصات
> (شاشات العمل العربية، مبدّل اللغة، تعديلات الحقول) حتى يمكن نقلها لأي موقع
> بأمر واحد بدلاً من إعادة ضبطها يدوياً.

---

## What the app contains

| Component | Location | Notes |
|---|---|---|
| Arabic workspaces (8) | `ndserp/fixtures/workspace.json` | حسابات، المبيعات، المشتريات، مخازن، الاصول، الملفات الرئيسية، HR، نقاط البيع |
| Module Manager/User Role Profiles | `ndserp/fixtures/role_profile.json` | 14 `* NDS` packs + owner packs; see README section below |
| Desk language switcher | `ndserp/public/js/language_switcher.bundle.js` | AR/EN toggle in the navbar, writes `User.language` |
| Workspace visibility policy | `ndserp/setup/workspace_policy.py` | Shows Ndserp workspaces, hides the rest |
| Field customisations | `ndserp/fixtures/property_setter.json` | Customize Form output for Sales Invoice, Purchase Order |
| Install / migrate hooks | `ndserp/install.py` | Re-applies the policy after every migrate |

### Requirements

- Frappe Framework v15
- ERPNext v15 — declared as `required_apps`, so bench refuses to install `ndserp` without it.

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/Amirmansi/ndserp --branch main
bench --site <your-site> install-app ndserp
bench build --app ndserp
bench --site <your-site> clear-cache
```

---

## ⚠️ The extra step required after **every** future change

This is the single most important rule in this repository.

Everything this app ships lives in the **database** of the working site
(workspaces, custom fields, property setters, print formats, scripts). Editing
them in the UI changes the site — it does **not** change the repository. If you
push without exporting, the change is lost the next time the app is installed
somewhere else.

**So after any change made through the Frappe UI, always run:**

```bash
bench --site <your-site> export-fixtures --app ndserp
```

Then review, commit and push:

```bash
cd apps/ndserp
git status                 # confirm ONLY the files you expected changed
git diff
git add -A
git commit -m "feat: <what changed>"
git push origin main
```

> **الخطوة الإضافية الإلزامية عند أي تحديث مستقبلي**
>
> كل ما يحمله التطبيق مخزَّن في قاعدة بيانات الموقع، وليس في ملفات المشروع.
> أي تعديل تقوم به من الواجهة (شاشة عمل، حقل، Property Setter، Print Format،
> Client Script) **لن يُحفظ في جيت هاب** إلا بعد تنفيذ الأمر التالي:
>
> ```bash
> bench --site <your-site> export-fixtures --app ndserp
> ```
>
> ثم راجع الملفات المتغيّرة وارفعها بـ `git add -A && git commit && git push`.
> بدون هذه الخطوة سيضيع التعديل عند تثبيت التطبيق على أي موقع آخر.

### Full update cycle

```bash
# 1. make your change in the Frappe UI on the working site
# 2. export it into the repo
bench --site <your-site> export-fixtures --app ndserp

# 3. review what actually changed
cd apps/ndserp && git status && git diff

# 4. if you touched JS/CSS
bench build --app ndserp

# 5. verify the change survives a round trip
bench --site <your-site> migrate
bench --site <your-site> clear-cache

# 6. publish
git add -A && git commit -m "feat: ..." && git push origin main
```

Step 5 matters: `bench migrate` re-imports the fixtures you just exported. If
something looks different afterwards, the export was incomplete.

---

## How to add something to the app

`bench export-fixtures` only exports what the filters in
[`ndserp/hooks.py`](ndserp/hooks.py) match. Set **Module = Ndserp** on the
record and it gets picked up automatically:

| You created | Do this so it is exported |
|---|---|
| Client Script / Server Script | Set **Module = Ndserp** on the script |
| Print Format | Duplicate it, set **Module = Ndserp** — never ship an ERPNext original |
| Report | Set **Module = Ndserp** |
| Workspace | Set **Module = Ndserp** |
| Customize Form change on a *new* doctype | Add the doctype to `CUSTOMISED_DOCTYPES` in `hooks.py` |
| Custom Field | Add its name (`Doctype-fieldname`) to `NDSERP_CUSTOM_FIELDS` in `hooks.py` |

Custom fields are whitelisted **by name**, not by doctype, and on purpose. Other
apps add fields to the same doctypes — `pos_next` owns `posa_pos_opening_shift`,
`posa_is_printed` and `pos_applied_one_time_rules` on Sales Invoice, and Frappe
owns `ta_amend_archived`. The old `dt`-based filter shipped all of them inside
`ndserp`, which made this app fight the app that actually owns each field on
every `bench migrate`.

### Fixture rules (do not break these)

The fixture list is deliberately narrow, and
[`ndserp/tests/test_fixtures.py`](ndserp/tests/test_fixtures.py) fails CI if it
is loosened:

1. **Never add a fixture without filters.** `{"dt": "Client Script"}` exports
   the client scripts of *every* installed app into this repo.
2. **Never ship records owned by another app** (`module` = Accounts, Regional,
   Selling …). Re-importing them overwrites the original app's copy on every
   `bench migrate`.
3. **Never ship `is_system_generated` records.** They are recreated by framework
   code and only cause conflicts.

---

## Workspace visibility policy

`bench migrate` re-syncs the workspaces shipped by Frappe, ERPNext and HRMS and
makes them visible again. `after_migrate` therefore re-applies the policy: the
six Ndserp workspaces are shown, every other workspace is set to
`public = 0, is_hidden = 1`.

```bash
# see what the policy would do, without changing anything
bench --site <site> execute ndserp.setup.workspace_policy.status

# apply manually (idempotent)
bench --site <site> execute ndserp.setup.workspace_policy.apply

# undo - make every workspace visible again
bench --site <site> execute ndserp.setup.workspace_policy.revert

# turn off the automatic run after migrate
bench --site <site> set-config -g ndserp_workspace_policy 0
```

If a user sees **empty** Arabic workspaces, their blocked modules are hiding the
links inside them:

```bash
bench --site <site> execute ndserp.setup.workspace_policy.clear_module_blocks \
  --kwargs '{"user": "someone@example.com"}'
```

---

## Module Manager / User Role Profiles

Day-to-day staff should use the single-module packs (never `System Manager`):

| Profile | Sees workspace | Can create users |
|---|---|---|
| `Sales Manager NDS` | المبيعات NDS ERP | Yes — only `Sales User NDS` |
| `Sales User NDS` | المبيعات NDS ERP | No |
| `Accounts Manager NDS` / `Accounts User NDS` | حسابات NDS ERP | Manager → Accounts User only |
| `Stock Manager NDS` / `Stock User NDS` | مخازن NDS ERP | Manager → Stock User only |
| `Purchase Manager NDS` / `Purchase User NDS` | المشتريات NDS ERP | Manager → Purchase User only |
| `Assets Manager NDS` / `Assets User NDS` | الاصول NDS ERP | Manager → Assets User only |
| `HR Manager NDS` / `HR User NDS` | HR NDS | Manager → HR User only |
| `POS Manager NDS` / `POS User NDS` | نقاط البيع NDS ERP | Manager → POS User only |

`POS Manager NDS` also includes `Accounts Manager`, `Accounts User`, and
`Item Manager` because on this stack POS Profile / Sales Invoice / Mode of
Payment are permissioned via Accounts roles, and Item write needs Item Manager.
Workspace scoping still keeps the desk on نقاط البيع only (no حسابات gate role).

Other packs were expanded the same way after a DocType-level audit
(`ndserp.setup.audit_nds_profiles.run`): Sales adds Sales Master Manager +
Accounts + Item Manager; Purchase adds Purchase Master Manager + Accounts User;
Assets adds Quality/Manufacturing roles; HR adds Expense Approver; Stock User
adds Item Manager. Re-run the audit anytime after permission changes.

Each Manager pack includes the helper role **`NDS Module Manager`**, which has
Custom DocPerm to create/read/write `User` and read `Role Profile`. The validate
hook in `ndserp.setup.user_provisioning` blocks assigning any other module pack
or `System Manager`.

**Owner packs** `Small Next` and `MID Next` still grant many modules at once.
They break single-workspace isolation by design — use them only for owners /
site admins, not for module staff.

### Assigning a module Manager (System Manager)

1. Create User → set Role Profile to e.g. `Sales Manager NDS` (do **not** add System Manager).
2. Save. The user sees only المبيعات and can open Sales DocTypes.
3. That manager opens **المستخدمين** on their workspace and creates a User with Role Profile `Sales User NDS`.

### Remapping existing live users (manual)

Do **not** bulk-change Role Profiles in migrate. For each operational user:

1. Decide their one module (Sales / Accounts / …).
2. Clear extra roles / gate roles.
3. Assign the matching `* Manager NDS` or `* User NDS` Role Profile.
4. Confirm desk shows only that Arabic workspace.

---

## Development

```bash
cd apps/ndserp
pre-commit install                        # ruff, eslint, prettier, pyupgrade
bench --site <site> set-config developer_mode 1
bench --site <site> run-tests --app ndserp
```

CI runs the test suite on every push to `main` and every pull request; the
Linters workflow runs Frappe Semgrep rules and `pip-audit`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A UI change disappeared after reinstalling elsewhere | `export-fixtures` was never run | Re-do the change, then export |
| English workspaces reappeared | Policy disabled, or migrate hook failed | `execute ndserp.setup.workspace_policy.apply`, check Error Log |
| Arabic workspaces are empty | User has blocked modules | `clear_module_blocks` (above) |
| Language switcher missing | Assets not rebuilt | `bench build --app ndserp && bench --site <site> clear-cache` |
| `git status` shows fixtures you did not touch | A filter is too broad | Tighten the filters in `hooks.py`, do not commit |

---

## License

MIT — see [license.txt](license.txt).
