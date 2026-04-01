# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Approval Workflows [Base]',
    'version': '1.1.5',
    'summary': """
    Dynamic, customizable and flexible approval workflows.
    Streamlining and optimizing your approvals and document processing.
    | dynamic approval module
    | Odoo approval system
    | flexible approval routes
    | document approval workflow
    | efficient document approvals
    | customizable approval stages
    | Odoo document management
    | multi-level approval process optimization
    | automated approval routes
    | dynamic document workflows
    | multilevel  approval route customization
    | seamless document processing
    | flexible document routing
    | dynamic approval stages
    | Odoo workflow enhancement
    | approval automation
    """,
    'category': 'Purchases,Sales,Accounting,Document Management,Productivity',
    'author': 'XFanis',
    'support': 'xfanis.dev@gmail.com',
    'website': 'https://xfanis.dev/odoo.html',
    'license': 'OPL-1',
    'price': 15,
    'currency': 'EUR',
    'description':
        """
Dynamic Approval Module for Odoo
================================
Empower Your Workflow with our Dynamic Approval Module for Odoo. Easily create customizable approval
routes for various documents, allowing seamless collaboration among multiple approvers. Define
conditions to include/exclude users, distribute responsibilities, and ensure timely approvals. Enjoy
flexible and efficient document authorization across your organization with our feature-rich Odoo
solution.
        """,
    'data': [
        # Access
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        # UI
        'views/menu.xml',
        'views/approval_route.xml',
        'views/approval_role.xml',
        'views/approval_route_document.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'data/demo/approval_roles.xml',  # Remove that line, if you do not need demo data
    ],
    'depends': [
        'base_setup',
        'product',
        'analytic',
        'xf_demo_data',  # Remove that dependency, if you do not need demo data
    ],
    'images': [
        'static/description/dynamic_approval_workflows.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
