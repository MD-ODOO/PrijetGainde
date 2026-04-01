# -*- coding: utf-8 -*-
{
    'name': 'Expense Approval | Dynamic Approval Workflows for Expenses',
    'version': '1.1.1',
    'summary': """
    Dynamic and flexible approval module for expense reports. 
    Streamlining and optimizing your approval workflows.
    | dynamic expense report approval 
    | flexible approval module for expenses 
    | expense report workflow 
    | customizable expense approval routes  
    | efficient expense report approvals 
    | automated approval process 
    | dynamic approval stages
    | flexible document workflows 
    | approval route customization
    | expense reports approval automation and optimization
    | dynamic approval workflow 
    | expense report routing enhancement 
    | expenses approval optimization, 
    | automated expense approvals
    | expense approval process | approve expense report    
    """,
    'category': 'Human Resources/Expenses,Generic Modules/Human Resources,Accounting',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 5,
    'currency': 'EUR',
    'description': """
Dynamic Approval Route for Expenses
===================================
This module helps to create multiple custom, flexible and dynamic approval route
for expense reports based on approval workflow settings.
    """,
    'data': [
        'views/res_config_settings_views.xml',
        'views/expense_approval_route.xml',
    ],
    'demo': [
        'data/demo/users.xml',
        'data/demo/approval_route.xml',
    ],
    'depends': [
        'xf_approval_route_base',
        'hr_expense',
    ],
    'images': [
        'static/description/dynamic_approval_workflows_expense.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
