{
    'name': 'API Orbus Infinity Gainde',
    'summary': "Intégration Orbus Infinity (GUPE) vers Odoo",
    'description': """
Module technique fournissant un client pour l'API Orbus Infinity / GUPE
(basket/panier, paiement) tel que décrit dans la collection Postman
`integration-odoo`.

Il gère :
- la configuration des URLs (auth, backendgateway, backendgupe) et identifiants ;
- l'obtention du token OAuth2 (Keycloak) ;
- des helpers Python pour :
  * lister les paniers (list-panier),
  * récupérer le détail d'un panier (detail-panier),
  * notifier un paiement (odoo/payer).

Aucune logique fonctionnelle Odoo n'est codée ici : ce module expose seulement
une API Python réutilisable par d'autres modules (ex. purchase_gainde).
""",
    'version': '18.0.1.0.0',
    'author': 'Gainde',
    'website': '',
    'category': 'Technical',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'api_orbus_gainde'],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/ir.model.access.csv',
        'views/infinity_panier_batch_wizard_views.xml',
        'views/infinity_panier_batch_views.xml',
        'views/infinity_api_config_views.xml',
        'views/account_payment_orbus_infinity_views.xml',
        'views/account_move_orbus_infinity_views.xml',
    ],
    'installable': True,
    'application': False,
}
