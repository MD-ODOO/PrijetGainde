{
    'name': 'HR GAINDE',
    'version': '1.3',
    'author': 'Mansour Diop /Consultant Odoo KILIFA',
    'category': 'HR Par KILIFA CONSULTING',
    'sequence': 10,
    'license': 'LGPL-3',
    'summary': 'Module RH complet : congés, notifications et demandes administratives',
    'description': """
Module de gestion RH pour GAINDE 2000 : congés, demandes médicales, notifications et gestion des postes et fonctions.
""",
    'website': '',
    'depends': [ 'base','hr','hr_contract','documents_hr','hr_holidays','report_xlsx' ],
    'data': [
        
        "views/employee_view.xml",
       
        "views/hr_cerco_category_view.xml",
    
        "security/ir.model.access.csv",
       

    ],
    'qweb': [],
    'demo': ["data/holidays_status.xml"
        ], 
    
    'test': [],
    'installable': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
