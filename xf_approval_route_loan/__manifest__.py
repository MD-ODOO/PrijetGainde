# -*- coding: utf-8 -*-
{
    'name': 'Loan Approval | Dynamic Approval Workflows for Employee Loans',
    'version': '1.0.0',
    'summary': """
    Dynamic and flexible approval module for employee loans. 
    Streamlining and optimizing your approval workflows.
    | dynamic employee loan approval 
    | flexible approval module for loans 
    | employee loan workflow 
    | customizable loan approval routes  
    | efficient employee loan approvals 
    | automated approval process 
    | dynamic approval stages
    | flexible document workflows 
    | approval route customization
    | employee loans approval automation and optimization
    | dynamic approval workflow 
    | employee loan routing enhancement 
    | loans approval optimization, 
    | automated loan approvals
    | loan approval process | approve employee loan    
    """,
    'category': 'Generic Modules/Human Resources,Accounting',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Employee Loans
=========================================
This module helps to create multiple custom, flexible and dynamic approval route
for employee loans based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/loan_approval_route.xml',
    ],
    'demo': [
        'data/demo/users.xml',
        'data/demo/approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base',
        'xf_loan',
    ],
    'images': [
        'static/description/dynamic_approval_workflows_loan.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
