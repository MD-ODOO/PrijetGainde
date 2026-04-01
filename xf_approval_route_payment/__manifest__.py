# -*- coding: utf-8 -*-
{
    'name': 'Payment Approval | Dynamic Approval Workflows for Payments',
    'version': '1.2.0',
    'summary': """
    Dynamic and flexible approval module for payments. 
    Streamlining and optimizing your approval workflows.
    | dynamic payment approval 
    | payments approval | payment approval process
    | payment workflow 
    | payment approval workflow	
    | dynamic payment approval stages
    | payment approval automation and optimization
    | automated payment approvals
    | payment approval process | approve payments    
    """,
    'category': 'Accounting/Accounting',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Payments
===================================
This module helps to create multiple custom, flexible and dynamic approval route
for payments based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/payment_approval_route.xml',
        'data/message_subtypes.xml',
    ],
    'demo': [
        'data/demo/users.xml',
        'data/demo/approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base',
        'account',
    ],
    'images': [
        'static/description/dynamic_approval_workflows_payment.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
