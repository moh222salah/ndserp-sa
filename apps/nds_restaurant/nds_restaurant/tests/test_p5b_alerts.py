# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P5b: realtime/audio alert plumbing for new KOTs (P5-T7) and per-minute delay notifications
(P5-T8). Isolated NDSUT fixtures only; the delay job is always scoped to the NDSUT profile."""

import os
from unittest import mock

import frappe
from frappe.utils import add_to_date, now_datetime

from nds_restaurant.api import kot as kot_api
from nds_restaurant.tests.test_helpers import add_user_to_test_branch, remove_user_from_test_branch
from nds_restaurant.tests.test_p4_roles import P4Base

JOB = "nds_restaurant.api.kot.check_kot_delays"


class P5bBase(P4Base):
	def setUp(self):
		super().setUp()
		kmeta = frappe.get_meta("NDS KOT")
		pmeta = frappe.get_meta("POS Profile")
		if not (
			kmeta.has_field("order_status")
			and kmeta.has_field("delay_notified")
			and pmeta.has_field("custom_notify_kot_delay")
			and pmeta.has_field("custom_recipients")
		):
			self.skipTest("P5 fields not migrated")
		self._started = now_datetime()
		self._orig = frappe.db.get_value(
			"POS Profile",
			self.pos_profile,
			["custom_notify_kot_delay", "custom_kot_warning_time", "custom_kot_audio_alert"],
			as_dict=True,
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(
			"Notification Log",
			{"document_type": "NDS KOT", "creation": (">=", self._started), "for_user": ("in", self._test_users())},
		)
		frappe.db.set_value("POS Profile", self.pos_profile, dict(self._orig))
		self._set_roles("custom_recipients", [])
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		super().tearDown()

	def _test_users(self):
		return [self.captain_a, self.captain_b, self.cashier, self.manager, self.kitchen, self.no_role]

	def _enable_delay(self, roles, minutes=1, notify=1):
		frappe.db.set_value(
			"POS Profile",
			self.pos_profile,
			{"custom_notify_kot_delay": notify, "custom_kot_warning_time": minutes},
		)
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		self._set_roles("custom_recipients", roles)

	def _backdate(self, kot, minutes=5):
		frappe.db.sql(
			"update `tabNDS KOT` set creation=%s where name=%s",
			(add_to_date(now_datetime(), minutes=-minutes), kot),
		)

	def _logs(self, kot, user=None):
		filters = {"document_type": "NDS KOT", "document_name": kot}
		if user:
			filters["for_user"] = user
		return frappe.get_all("Notification Log", filters=filters, fields=["for_user", "subject", "type"])

	def _kot_for(self, table):
		self._as(self.captain_a)
		inv = self._order(table=table, generate_kot=1)["invoice"]
		frappe.set_user("Administrator")
		return frappe.get_all("NDS KOT", filters={"pos_invoice": inv, "docstatus": 1}, pluck="name")[0]


class TestP5bDelayNotifications(P5bBase):
	def test_hook_runs_every_minute(self):
		events = frappe.get_hooks("scheduler_events")
		self.assertIn(JOB, events.get("cron", {}).get("* * * * *", []))
		self.assertNotIn(JOB, events.get("hourly", []))
		job = frappe.db.get_value("Scheduled Job Type", {"method": JOB}, ["frequency", "cron_format"], as_dict=True)
		if job:  # synced on migrate
			self.assertEqual(job.frequency, "Cron")
			self.assertEqual(job.cron_format, "* * * * *")

	def test_one_alert_per_kot_for_seated_role_holders_only(self):
		self._enable_delay(["NDS Captain"])
		kot = self._kot_for(self.t1)
		self._backdate(kot)
		remove_user_from_test_branch(self.branch, self.captain_b)
		try:
			with mock.patch("frappe.publish_realtime") as pub:
				kot_api.check_kot_delays(self.pos_profile)
		finally:
			add_user_to_test_branch(self.branch, self.captain_b)
		logs = self._logs(kot)
		self.assertEqual([l.for_user for l in logs], [self.captain_a])
		subject = logs[0].subject
		self.assertIn(kot, subject)
		self.assertIn(self.production_unit_name, subject)
		self.assertIn(self.t1, subject)
		self.assertIn("delayed 5 min", subject)
		self.assertEqual(logs[0].type, "Alert")
		self.assertEqual(frappe.db.get_value("NDS KOT", kot, "delay_notified"), 1)
		delay_calls = [c for c in pub.call_args_list if c.args and c.args[0] == "nds_kot_delay"]
		self.assertEqual(len(delay_calls), 1)
		self.assertEqual(delay_calls[0].args[1]["kot"], kot)
		self.assertEqual(delay_calls[0].args[1]["production_unit"], self.production_unit_name)
		# Alert-type logs never email, so nothing is queued for the recipient.
		self.assertFalse(
			frappe.db.exists("Email Queue", {"creation": (">=", self._started), "message": ("like", f"%{kot}%")})
		)
		# a minute later: no duplicate
		kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(len(self._logs(kot)), 1)

	def test_served_fresh_and_disabled_are_skipped(self):
		self._enable_delay(["NDS Captain"])
		served = self._kot_for(self.t1)
		fresh = self._kot_for(self.t2)
		self._backdate(served)
		self._as(self.manager)
		kot_api.serve_kot(served)
		frappe.set_user("Administrator")
		kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(self._logs(served), [])
		self.assertEqual(self._logs(fresh), [])
		self.assertEqual(frappe.db.get_value("NDS KOT", fresh, "delay_notified"), 0)

		# setting off -> silent even when late
		self._backdate(fresh)
		self._enable_delay(["NDS Captain"], notify=0)
		kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(self._logs(fresh), [])
		self.assertEqual(frappe.db.get_value("NDS KOT", fresh, "delay_notified"), 0)

	def test_warning_time_is_respected(self):
		self._enable_delay(["NDS Captain"], minutes=10)
		kot = self._kot_for(self.t1)
		self._backdate(kot, minutes=5)
		kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(self._logs(kot), [])
		self._backdate(kot, minutes=11)
		kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(len(self._logs(kot, self.captain_a)), 1)

	def test_job_is_a_noop_without_p5_fields(self):
		"""Shared code runs on sites that were never migrated; the guard must stop the job there."""
		self._enable_delay(["NDS Captain"])
		kot = self._kot_for(self.t1)
		self._backdate(kot)
		real = frappe.get_meta

		class _NoField:
			def __init__(self, meta):
				self._meta = meta

			def has_field(self, fieldname):
				return False if fieldname == "delay_notified" else self._meta.has_field(fieldname)

		with mock.patch.object(
			kot_api.frappe, "get_meta", side_effect=lambda dt, *a, **k: _NoField(real(dt)) if dt == "NDS KOT" else real(dt, *a, **k)
		):
			kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(self._logs(kot), [])
		with mock.patch.object(kot_api.frappe.db, "table_exists", return_value=False):
			kot_api.check_kot_delays(self.pos_profile)
		self.assertEqual(self._logs(kot), [])


class TestP5bNewKotAlert(P5bBase):
	def test_new_kot_publishes_realtime_event(self):
		with mock.patch("frappe.publish_realtime") as pub:
			kot = self._kot_for(self.t1)
		calls = [c for c in pub.call_args_list if c.args and c.args[0] == "nds_new_kot"]
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0].args[1]["kot"], kot)
		self.assertEqual(calls[0].args[1]["production_unit"], self.production_unit_name)
		self.assertTrue(calls[0].kwargs.get("after_commit"))

	def test_kds_context_carries_audio_settings_and_default_sound_ships(self):
		self.assertTrue(
			os.path.exists(frappe.get_app_path("nds_restaurant", "public", "sounds", "kot.mp3"))
		)
		frappe.db.set_value("POS Profile", self.pos_profile, "custom_kot_audio_alert", 1)
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		ctx = kot_api.get_kds_context(self.production_unit_name)
		self.assertEqual(ctx["kot_audio_alert"], 1)
		self.assertIn("kot_alert_sound", ctx)
