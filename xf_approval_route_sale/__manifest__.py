# -*- coding: utf-8 -*-

{
    'name': 'Sale Approval | Dynamic Approval Workflows for Sales',
    'version': '1.1.1',
    'summary': """
    Dynamic and flexible approval module for sale orders. 
    Streamlining and optimizing your approval workflows.
    | dynamic sale order approval 
    | flexible approval module 
    | sale order workflow 
    | customizable approval routes  
    | efficient sale order approvals 
    | automated approval process 
    | dynamic approval stages
    | flexible document workflows 
    | approval route customization
    | sale order approval automation and optimization
    | dynamic approval workflow 
    | sale order routing enhancement 
    | sale order approval optimization, 
    | automated sale approvals
    | SO approval process | approve SO | approve sale order    
    """,
    'category': 'Sales',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Sales
================================
This module helps to create multiple custom, flexible and dynamic approval route
for sale orders based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/sale_approval_route.xml',
        'data/message_subtypes.xml',
    ],
    'demo': [
        'data/demo/users.xml',
        'data/demo/approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base',
        'sale_management',
    ],
    'images': [
        'static/description/dynamic_approval_workflows_sale.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
