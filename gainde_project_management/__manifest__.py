{
    'name': 'Gainde project Management',
    'version': '1.0.0',
    'category': 'Services',
    'summary': 'Gestion avancée des projets avec intégrations des outills supplementaires',
    'author': 'Issakha Diallo',
    'depends': ['project','project_enterprise', 'hr_timesheet', 'account',
                'purchase', 'analytic','sale_timesheet', 'documents', 'planning',
                'sale', 'hr','account_budget', 'sale_management','purchase_request',
                'purchase_requisition',  'mail', 'pk_advance_employee_portal',
                'purchase_gainde',],
    'data': [
        'security/project_security.xml',
        'security/ir.model.access.csv',

        'data/config/user_profiles_config.xml',

        'data/cron.xml',
        'data/mail_template_data.xml',

        'views/project_views.xml',
        'views/project_task_views.xml',
        'views/planning_views.xml',
        'views/purchase_views.xml',
        'views/hr_employee_views.xml',

        'views/project_dashboard.xml',
        'views/assign_project_wizard_views.xml',
        'views/project_invoice_wizard_views.xml',

    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
