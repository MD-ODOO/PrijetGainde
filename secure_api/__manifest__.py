# -*- coding: utf-8 -*-
{
    "name": "Secure API - REST APIs with OAuth 2.0 & JWT authentication",
    "summary": """Transform Odoo into an API-first powerhouse - Secure REST endpoints in minutes""",
    "description": """Unleash the full potential of your Odoo data with enterprise-grade API-first architecture. Create secure REST endpoints, implement OAuth2.0 & JWT authentications, export to Postman & Swagger - all without complex setup or external dependencies.""",
    "author": "minhng.info",
    "website": "https://minhng.info",
    "license": "OPL-1",
    "category": "Extra Tools",
    "version": "18.0.0.4",
    "depends": [
        "base",
        "web",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/secure_api_views.xml",
        "views/secure_api_category_views.xml",
        "views/secure_api_tag_views.xml",
        "views/secure_api_app_views.xml",
        "views/secure_api_endpoint_views.xml",
        "views/secure_api_test_views.xml",
        "views/ir_model_views.xml",
        "views/res_config_settings_views.xml",
        "views/secure_api_stats_views.xml",
        "wizard/export_postman_collection_wizard_views.xml",
        "wizard/export_swagger_wizard_views.xml",
        "data/data.xml",
        "data/ir_cron_data.xml",
    ],
    "demo": [
        "data/data_demo.xml",
    ],
    ## Upgraded by Terraform
    "assets": {
        'web.assets_backend': [
            'secure_api/static/src/scss/secure_api.scss',
            'secure_api/static/src/components/btn_live_test/*',
            'secure_api/static/src/components/btn_expose_api/*',
        ],
    },
    ## End of assets section
    "post_load": "_secure_model_exe",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
    "images": ["static/description/banner.png"],
    "price": "55.99",
    "currency": "EUR",
    "live_test_url": "",
}
