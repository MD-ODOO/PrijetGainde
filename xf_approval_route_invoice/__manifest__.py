# -*- coding: utf-8 -*-

{
    'name': 'Invoice Approval | Dynamic Approval Workflows for Invoices',
    'version': '1.2.1',
    'summary': """
    Dynamic and flexible approval module for invoices and bills. 
    Streamlining and optimizing your approval workflows.
    | dynamic invoice approval 
    | dynamic bill approval 
    | flexible approval module 
    | invoice workflow 
    | customizable approval routes  
    | efficient bill approvals 
    | automated approval process 
    | dynamic approval stages
    | flexible document workflows 
    | approval route customization
    | invoice approval automation and optimization
    | dynamic approval workflow 
    | invoice routing enhancement 
    | invoices approval optimization, 
    | automated billing approvals
    | Invoice approval process | approve invoice | approve bill    
    """,
    'category': 'Accounting/Accounting',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Invoices and Bills
=============================================
This module helps to create multiple custom, flexible and dynamic approval route
for invoices based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/account_move_approval_route.xml',
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
        'static/description/dynamic_approval_workflows_invoice.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
