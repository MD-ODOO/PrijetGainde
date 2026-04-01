# -*- coding: utf-8 -*-
{
    'name': "BC Gainde",
    'summary': """
        Edition du bon de commande selon le format Gainde 2000""",

    'description': """
        Edition du bon de commande selon le format Gainde 20
    """,

    'author': "Kilifa",
    'website': "https://www.kilifa.fr",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    # any module necessary for this one to work correctly
    'depends': ['base','purchase'],
    'license': 'LGPL-3',
        'data' : [ 
         'report/report.xml',
         'views/gainde_external_layout.xml',
         'views/gainde_header_footer.xml',
         'views/gainde_report.xml',
         'views/purchase_order_form_inherit.xml',
    ],
    # always loaded
   
    # only loaded in demonstration mode
    
   
}
