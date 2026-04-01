{
    'name': 'Portal Purchase Request',
    'version': '1.0',
    'description': 'Purchase request with the portal user',
    'summary': 'Use this module to have notification of requirements of '
    'materials and/or external services and keep track of such from portal user',
    'author': 'BuildFish',
    'website': 'http://www.build-fish.com/',
    'license': 'LGPL-3',
    'category': 'Purchase Management',
    'depends': [
        'web',
        'portal',
        'purchase_request',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_request_views.xml',
        'views/purchase_requests_portal_templates.xml',

    ],
    "assets": {
        'web.assets_frontend': [
            'bf_portal_purchase_request/static/src/scss/portal.scss',
            'bf_portal_purchase_request/static/src/js/portal.js',
            'bf_portal_purchase_request/static/src/xml/purchase_request.xml',
            'bf_portal_purchase_request/static/lib/select2/select2.css',
            'bf_portal_purchase_request/static/lib/select2-bootstrap-css/select2-bootstrap.css',
            'bf_portal_purchase_request/static/lib/select2/select2.js',
        ],
    },
    'images': [
        'static/description/main_screenshot.png',
    ],
    'live_test_url': 'https://youtu.be/jyELlouEq1o',
    'price': 100.00,
    'currency': 'USD',
    'installable': True,
}

# El módulo fue diseñado con el propósito de optimizar costos relacionados con licencias de usuarios.
# Permite gestionar requerimientos realizados por usuarios que no necesitan acceso completo al sistema,
# evitando así la necesidad de adquirir licencias adicionales para ellos.
