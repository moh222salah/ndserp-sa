# Installation

    cd ~/frappe-bench
    bench get-app /path/to/optical_app          # or copy the folder to apps/ and pip install -e
    bench --site <site> install-app optical     # ERPNext must already be installed
    bench --site <site> migrate
    bench build --app optical
    bench --site <site> set-config developer_mode 0

The install creates roles, role profiles, Item custom fields and two service items (OPT-INSURANCE, OPT-LAB-SERVICE),
all re-checked on every migrate. Set language to Arabic per user or in System Settings.
Assign users a Role Profile (Optical Cashier, Optician, ...). Restrict branches with User Permissions on
Warehouse and Cost Center.
