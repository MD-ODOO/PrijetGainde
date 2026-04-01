{
    "name": "Employee Self Service RH (Enterprise)",
    "version": "18.0.2.0.0",
    "summary": "Self-service RH Employé – Odoo 18 Enterprise (Mail Python)",
    "category": "Human Resources",
    "author": "Mano Diop",
    "depends": ["hr", "hr_payroll", "hr_contract", "mail"],
    "data": [
       #"security/employee_rules.xml",
       # "security/ir.model.access.csv",
        "data/cron.xml",
        "views/employee_menu.xml",
        "views/payslip_views.xml"
    ],
    "installable": True,
    "application": False
}