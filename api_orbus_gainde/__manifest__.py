{
    'name': 'API Orbus Gainde',
    'summary': "Intégration API Orbus Classic vers Odoo",
    'description': """
Module technique fournissant un client générique pour l'API Orbus Classic
(https://orbus-preprod.gainde2000.sn:8083/APIORBUSODOO).

Il gère :
- la configuration (URL, identifiants) par société ;
- l'authentification (login) et le stockage du token ;
- des helpers Python pour appeler les principaux endpoints (dossier, client, factures).

Ce module ne crée pas de logique métier propre : il expose une API Python
réutilisable par d'autres modules (ex. purchase_gainde).
""",
    'version': '18.0.1.0.0',
    'author': 'Gainde',
    'website': '',
    'category': 'Technical',
    'license': 'LGPL-3',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/orbus_api_config_views.xml',
        'views/account_payment_orbus_views.xml',
        'views/orbus_invoice_wizard_views.xml',
        'views/orbus_facture_batch_views.xml',
        'data/orbus_api_config_data.xml',
        'data/orbus_cron.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
