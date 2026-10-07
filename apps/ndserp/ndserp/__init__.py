__version__ = "1.0.0"


def _patch_workspace_scope():
	# Runs once per worker process, at import time - see
	# ndserp.setup.workspace_scope for why this needs a monkeypatch rather than
	# a stock hook (no hook exists for "hide this workspace FROM role X").
	# Guarded so a frappe upgrade that removes `Workspace.is_permitted` fails
	# soft (falls back to stock behaviour) instead of breaking app import for
	# every worker on the site.
	try:
		from ndserp.setup.workspace_scope import patch_workspace_permission

		patch_workspace_permission()
	except Exception:
		# No site/db context is guaranteed at import time, so don't try to
		# frappe.log_error here - just leave stock Workspace.is_permitted in
		# place and let the app carry on.
		pass


_patch_workspace_scope()
