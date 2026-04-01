# -*- coding: utf-8 -*-
# Irfan Ullah Odoo Developer
# contact Whatsapp: +923349693796 Email: irfanbcs797@gmail.com
# YouTube: https://www.youtube.com/@irfanullah
{
    'name': "Advance Employee Portal",

    'summary': "Employee Portal, Advance Employee Portal, Attendance Portal, Employee Time Off/Leave Portal, Employee Expense Portal, Timesheet Portal, PaySlip/PayRoll Portal, Employee Weekly Schedule Portal, Employee Profile Portal, Employee Project Tasks Portal, Employee Sale Portal, CRM Portal, All in one Employee Portal, HR Portal ...more",
    'description': "Employee Portal, Advance Employee Portal, Attendance Portal, Employee Time Off/Leave Portal, Employee Expense Portal, Timesheet Portal, PaySlip/PayRoll Portal, Employee Weekly Schedule Portal, Employee Profile Portal, Employee Project Tasks Portal, Employee Sale Portal, CRM Portal, All in one Employee Portal, HR Portal  ...more",

    'author': "Irfan Ullah",
    'website': "https://www.youtube.com/@irfanullah",
    'category': 'Human Resources',
    'license' : 'OPL-1',
    'version': '18.0.0.1',
    'price': '105',
    'currency': 'EUR',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale_management', 'portal', 'hr_holidays', 'hr_expense', 'hr_payroll', 'planning','project', 'hr', 'hr_skills', 'hr_attendance', 'stock', 'hr_timesheet', 'crm'],

    # always loaded
    'data': [
        'security/user_groups.xml',
        'security/ir.model.access.csv',
        'security/portal_access.xml',
        'views/new_menus_in_portal.xml',
        'views/employee_leave_template.xml',
        'views/no_emp_linked_tem.xml',
        'views/weekly_schedule_template.xml',
        'views/attendance_templates.xml',
        'views/project_tasks.xml',
        'views/sale_order.xml',
        'views/hr_expense.xml',
        'views/emp_profile.xml',
        'views/pay_slip.xml',
        'views/portal_crm_templates.xml',
        'views/timesheet_template.xml',
        'views/inherit_backend_views.xml',
    ],
    'images': ['static/description/banner.png'],

    'application': True,
    'installable': True,
    'auto_install': False,
}
