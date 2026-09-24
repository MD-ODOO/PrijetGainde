# -*- coding: utf-8 -*-
{
    'name': 'GAINDE - Simulation de salaire net',
    'version': '18.0.1.0.0',
    'author': 'Mansour Diop / KILIFA CONSULTING',
    'category': 'Human Resources/Payroll',
    'summary': 'Simulation inverse du salaire net négocié au Sénégal',
    'description': """
Simulation de salaire net pour les négociations RH.

Le simulateur part du salaire net à atteindre et recherche le brut correspondant,
en tenant compte uniquement des éléments suivants :
- Salaire de base
- Sursalaire
- IR
- TRIMF
- IPRES RG
- IPRES RC (cadre uniquement)
- Transport fixe de 26 000 FCFA

Les données familiales servent à déterminer les parts IR et les personnes prises
en compte pour la TRIMF. Aucun calcul CSS, CFCE ou charge patronale n'est effectué.
""",
    'depends': [
        'hr',
        'hr_contract',
        'hr_payroll',
        'paie_gainde',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/salary_category_data.xml',
        'views/salary_category_views.xml',
        'views/salary_simulation_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
