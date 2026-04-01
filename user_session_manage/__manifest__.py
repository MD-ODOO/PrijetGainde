# -*- coding: utf-8 -*-
######################################################################
#                                                                    #
# Part of EKIKA CORPORATION PRIVATE LIMITED (Website: ekika.co).     #
# See LICENSE file for full copyright and licensing details.         #
#                                                                    #
######################################################################

{
    'name': 'User Session Management v18.0',
    'summary': """The User Session Management module enhances Odoo's session control by allowing administrators to set session limits and expiry configurations for individual users. With features like tracking login history, managing active sessions across devices, and enabling session restrictions, this module provides better security and control over user access and activity.
        Odoo session management
        User session control Odoo
        User Session Management
        Odoo active session tracking
        Session limit configuration Odoo
        Odoo login history tracking
        Secure user sessions Odoo
        Manage user sessions Odoo
    """,
    'company': 'EKIKA CORPORATION PRIVATE LIMITED',
    'author': 'EKIKA',
    'website': 'https://ekika.co',
    'category': 'Extra Tools,Tools',
    'version': '18.0.1.0',
    'license': 'OPL-1',
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_user_views.xml',
        'views/user_login_history.xml',
        'views/user_session_detail.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'user_session_manage/static/src/login_notification_service.js',
            'user_session_manage/static/src/user_menu_items.js',
        ]
    },
    'live_test_url': 'https://user_session_manage-18.demo.odoo-apps.ekika.co/web/login?module=user_session_manage-18',
    'images': ['static/description/banner.gif'],
    'price': 17.25,
    'currency': 'EUR',
    'description': """
    """
}
