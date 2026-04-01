{
    'name': 'Secure Error Handling',
    'version': '1.0',
    'summary': 'Masque les erreurs techniques côté interface',
    'author': 'Odoo',
    'depends': ['base', 'web'],
    'data': [
        'views/res_config_settings_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'secure_error_handling/static/src/js/error_handler.js',
        ],
    },
    'installable': True,
    'application': False,
}
