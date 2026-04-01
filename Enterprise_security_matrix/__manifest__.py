{
    'name': 'Enterprise Security Matrix',
    'version': '18.0.1.0.0',
    'category': 'Security',
    'summary': 'Advanced security matrix for PME with 200 users',
    'depends': [
        'base',
        'account',
        'hr',
        'hr_contract',
    ],
    'data': [
        'security/groups.xml',
        'security/account_rules.xml',
        'security/hr_rules.xml',
        'security/ir.model.access.csv',
        'views/res_users_view.xml',
    ],
    'installable': True,
    'application': False,
}