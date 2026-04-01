{
    'name': 'URL Firewall',
    'version': '1.0',
    'summary': 'Bloque les accès directs aux URLs sensibles sauf administrateurs et utilisateurs autorisés',
    'author': 'Toi',
    'depends': ['base', 'web', 'base_setup'],
    'data': [
        'security/groups.xml',
        'views/res_config_settings_view.xml',
    ],
}
