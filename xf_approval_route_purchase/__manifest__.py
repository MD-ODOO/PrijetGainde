# -*- coding: utf-8 -*-
{
    'name': 'Purchase Approval | Dynamic Approval Workflows for Purchases',
    'version': '1.1.2',
    'summary': """
    Dynamic and flexible approval module for purchase orders. 
    Streamlining and optimizing your approval workflows.
    | dynamic purchase order approval 
    | purchase approval | PO approval process
    | requisition approval | RFQ approval
    | purchase order workflow 
    | purchase order approval workflow	
    | customizable approval routes  
    | efficient purchase order approvals 
    | automated approval process 
    | dynamic purchase approval stages
    | PO approval route customization
    | purchase order approval automation and optimization
    | dynamic PO approval workflow 
    | purchase order routing enhancement 
    | purchase order approval optimization, 
    | automated purchase approvals
    | PO approval process | approve PO    
    """,
    'category': 'Purchases',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Purchases
====================================
This module helps to create multiple custom, flexible and dynamic approval route
for purchase orders based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/purchase_approval_route.xml',
    ],
    'demo': [
        'data/demo/users.xml',
        'data/demo/approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base',
        'purchase',
    ],
    'images': [
        'static/description/dynamic_approval_workflows_purchase.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
