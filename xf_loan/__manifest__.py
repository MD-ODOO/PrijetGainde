# -*- coding: utf-8 -*-
{
    'name': 'Employee Loan Management',
    'version': '1.0.0',
    'summary': """
    Effortlessly manage employee loans and streamline loan approval workflows. 
    The perfect solution for simplified and efficient loan processing.
    | HR Loan Management
    | employee loans
    | loan approval 
    | HR loan processing
    | HR loan system
    | loan requests and approval
    | employee loan approval workflows
    | loan disbursement
    | employee loan repayment 
    | approve employee loan request 
    | approve loan request 
    """,
    'category': 'Generic Modules/Human Resources',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 15,
    'currency': 'EUR',
    'description':
        """
        Employee Loan System.
        Optimize your employee financial support with our Odoo Loan Management Module. 
        Streamline loan requests, approvals, and repayments effortlessly.
        """,
    'data': [
        # Access
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        # UI
        'views/menu.xml',
        'wizard/loan_request.xml',  # Should be before views, because external reference
        'wizard/loan_installment.xml',  # Should be before views, because external reference
        'views/loan_request.xml',
        'views/res_config_settings_views.xml',
        # Data
        'data/ir_sequence.xml',
        'data/message_subtypes.xml',
    ],
    'demo': [
        'data/demo/users.xml',  # Remove that line, if you do not need demo data
    ],
    'depends': [
        'hr','hr_payroll',
        'xf_mail_helper',
        'xf_demo_data',  # Remove that dependency, if you do not need demo data
    ],
    'images': [
        'static/description/xf_loan.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
