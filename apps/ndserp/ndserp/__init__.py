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
		from ndserp.setup.custom_report_policy import patch_custom_report_section

		patch_workspace_permission()
		patch_custom_report_section()
	except Exception:
		# No site/db context is guaranteed at import time, so don't try to
		# log an error here. The before_request hooks retry both patches if
		# early import fails.
		pass


_patch_workspace_scope()
