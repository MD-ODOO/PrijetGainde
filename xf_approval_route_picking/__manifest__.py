# -*- coding: utf-8 -*-

{
    'name': 'Transfer Approval | Dynamic Approval Workflows for Transfers',
    'version': '1.1.1',
    'summary': """
    Dynamic and flexible approval module for transfers. 
    Streamlining and optimizing your approval workflows.
    | dynamic transfer approval 
    | transfers approval | transfer approval process
    | receipts approval | receipt approval process
    | deliveries approval | delivery approval process
    | transfer workflow 
    | transfer approval workflow	
    | stock picking approval workflow	
    | dynamic transfer approval stages
    | transfer approval automation and optimization
    | automated transfer approvals
    | transfer approval process | approve transfers  
    """,
    'category': 'Inventory/Inventory',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Transfers
================================
This module helps to create multiple custom, flexible and dynamic approval route
for transfers (receipts and deliveries) based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/approval_route.xml',
        'data/message_subtypes.xml',
    ],
    'demo': [
        'data/demo/users.xml',
        'data/demo/approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base',
        'stock',
    ],
    'images': [
        'static/description/dynamic_approval_workflows_picking.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
