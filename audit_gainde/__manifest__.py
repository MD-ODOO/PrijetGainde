# -*- coding: utf-8 -*-
{
    'name': "Audit Gainde",

    'summary': "Module d'audit et conformité pour le système Gainde2000",
    'sequence': 5,
    'license': 'LGPL-3',
    'description': """
     Module d'audit et conformité pour le système Gainde2000
    """,

    'author': "Papa Daouda FAYE Consultant Odoo(KILIFA CONSULTING)",
    'website': "https://www.kilifa.fr/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','mail','hr','web','spreadsheet_dashboard'],

    # always loaded
    'data': [
        'security/audit_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/audit_domain_data.xml',
      #  'data/audit_plan_data.xml',
      #  'data/audit_mission_data.xml',
      #  'data/audit_risk_data.xml',
        'data/cron.xml',
        'data/email_templates.xml',
        'views/audit_plan.xml',
        'views/audit_domain.xml',
        'views/audit_mission.xml',
        'views/audit_risk.xml',
        'views/audit_finding.xml',
        'views/audit_recommandation.xml',
        'views/audit_corrective_action.xml',
        'views/audit_control.xml',
        'reports/report_plan_template.xml',
        'reports/report_mission_template.xml',
        'reports/audit_report_action.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
            'web.assets_backend': [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
                'audit_gainde/static/src/css/executive_dashboard.css',
                'audit_gainde/static/src/js/executive_dashboard.js',
                'audit_gainde/static/src/xml/executive_dashboard.xml',
            ],
        },
    'installable': True,
    'application': True,
    'auto_install': False,
}

