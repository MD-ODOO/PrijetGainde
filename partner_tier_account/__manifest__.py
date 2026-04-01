{
    'name': 'Partner Tier Account',
    'version': '18.0.1.0.0',
    'category': 'Contacts',
    'summary': 'Add unique tier account field to partners',
    'description': """
        This module extends the res.partner model to add a tier_account field.
        The tier account is unique per partner.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['base','account','purchase'],
    'data': [
        'data/account_move_sequence.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}