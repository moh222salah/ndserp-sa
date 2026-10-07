app_name = "gas_station"
app_title = "Gas Station"
app_publisher = "Ahmed"
app_description = "Gas Station Operations & PTS-2 Monitoring for ERPNext v16"
app_email = "dev@example.com"
app_license = "MIT"

# ERPNext is the business/financial system of record. Do not duplicate it.
required_apps = ["erpnext"]

# ---------------------------------------------------------------------------
# Install / migrate
# ---------------------------------------------------------------------------
after_install = "gas_station.setup.install.after_install"
after_migrate = "gas_station.setup.install.after_migrate"

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
# - watchdog: flag controllers/equipment Stale when packets stop arriving.
# - simulator tick: emit due mock packets for running Mock PTS Controllers only.
#   Both are bounded and safe to run every minute.
scheduler_events = {
    "cron": {
        "* * * * *": [
            "gas_station.gas_station.integration.watchdog.mark_stale_controllers",
            "gas_station.gas_station.simulator.engine.tick",
        ],
    },
}

# ---------------------------------------------------------------------------
# Fixtures — export the operational Roles with the app.
# ---------------------------------------------------------------------------
fixtures = [
    {
        "doctype": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "Gas Station Administrator",
                    "Gas Station Integration Manager",
                    "Station Manager",
                    "Station Operator",
                    "Gas Station Viewer",
                ],
            ]
        ],
    }
]
