app_name = "amir_theme_v16"
app_title = "Amir Theme v16"
app_publisher = "Eng. Amir Mansi"
app_description = "Professional bilingual (AR/EN) ERP theme for ERPNext v16"
app_email = "amirahmd12300@gmail.com"
app_license = "MIT"
frappe_version = ">=16.0.0 <17.0.0"
categories = ["Customization", "UI/UX"]

app_include_css = "amir_theme.bundle.css"
app_include_js = "amir_theme.bundle.js"

web_include_css = "login_brand.bundle.css"
web_include_js = "login_brand.bundle.js"

extend_bootinfo = "amir_theme_v16.boot.extend_bootinfo"
update_website_context = "amir_theme_v16.website.update_website_context"

after_install = "amir_theme_v16.install.after_install"
after_migrate = "amir_theme_v16.install.after_migrate"
