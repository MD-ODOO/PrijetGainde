# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

{
    'name': 'All in One Helpdesk Enterprise | Helpdesk Ticket Management',
    'version': '18.0.1.0',
    'sequence': 1,
    'category': 'Generic Modules/Helpdesk',
    'description':
        """
All in One Helpdesk Odoo app, your ultimate tool for managing customer support and internal requests with ease. This app brings together all the essential helpdesk features in one place, making it simple for both customers and employees to raise and manage tickets. Whether a customer has a complaint, a request for improvement, or needs to track their issue, they can easily do so through the website portal. The app also lets customers sign, cancel, or close tickets directly from the portal, and track their ticket status in real-time.

With features like Helpdesk Document, you can quickly see all the documents attached to a ticket, and with Helpdesk Solution, you can add detailed solutions with images once an issue is resolved. The app also includes time-tracking tools, allowing users to start and stop a timer when working on a ticket. You can assign multiple users to a ticket, create sub-tickets, and even merge similar tickets into one. Plus, you’ll receive reminders before a ticket is due, and a notification will be sent when a new ticket is created.

For those handling multiple tickets, the app allows mass assignment, updates, and tagging, streamlining the process. It also keeps a history of how long a ticket stayed in each stage, ensuring full transparency. Finally, you can configure WhatsApp message templates to communicate directly with customers from the Helpdesk Ticket, making it easier than ever to stay in touch and keep everyone informed.

This app is designed to make managing helpdesk tickets straightforward and efficient, perfect for businesses of all sizes.     
          
All in One Helpdesk HelpDesk Customizable Help Desk Service Desk HelpDesk With Stages Help Desk Ticket Management Helpdesk Email Templates Email Alias Email Helpdesk Chatter Sale Order With Helpdesk Purchase Order With Helpdesk Invoice With Helpdesk Whatsapp Custom Stages Helpdesk CRM helpdesk Timesheet Helpdesk Helpdesk Website Request Helpdesk Portal Signature Helpdesk Portal Cancel Close Ticket Helpdesk Ticket Tracking Helpdesk Document HelpDesk Solution Helpdesk Start End Time Helpdesk Multi User Helpdesk due Reminder Helpdesk Sub Ticket Merge Helpdesk Ticket Helpdesk Ticket Stage Change History Helpdesk Mass Assign Tickets Helpdesk Mass Update Tickets Helpdesk Mass Update Tags Helpdesk User Notification Configure WhatsApp message template

    """,
    'summary': 'All in One Helpdesk HelpDesk Customizable Help Desk Service Desk HelpDesk With Stages Help Desk Ticket Management Helpdesk Email Templates Email Alias Email Helpdesk Chatter Sale Order With Helpdesk Purchase Order With Helpdesk Invoice With Helpdesk Whatsapp Custom Stages Helpdesk CRM helpdesk Timesheet Helpdesk Helpdesk Website Request Helpdesk Portal Signature Helpdesk Portal Cancel Close Ticket Helpdesk Ticket Tracking Helpdesk Document HelpDesk Solution Helpdesk Start End Time Helpdesk Multi User Helpdesk due Reminder Helpdesk Sub Ticket Merge Helpdesk Ticket Helpdesk Ticket Stage Change History Helpdesk Mass Assign Tickets Helpdesk Mass Update Tickets Helpdesk Mass Update Tags Helpdesk User Notification Configure WhatsApp message template',
    'depends': ['helpdesk','project','website','portal','website_hr_recruitment','web','attachment_indexation','hr_expense', 'survey','maintenance','hr','crm','crm_helpdesk','purchase_gainde'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/tickets_sequence_view.xml',
        'data/mail_template.xml',
        'data/cron.xml',
        'data/template_survey_start.xml',
        'data/website_menu.xml',
        'data/helpdesk_data.xml',
        'views/helpdesk_ticket_inherit.xml',
        'views/helpdesk_team_view.xml',
        'wizard/helpdesk_ticket_templates.xml',
        'wizard/ticket_tag_wizard.xml',
        'wizard/mass_update_ticket_views.xml',
        'wizard/mass_assign_ticket_views.xml',
        'wizard/helpdesk_whatsapp_wizard.xml',
        'views/dev_helpdesk_ticket.xml',
        'views/hide_crm_helpdesk_buttons.xml',
        'views/helpdesk_ticket_kanban_inherit.xml',
        'views/project_task.xml',
        'views/helpdesk_ticket_portal.xml',
        'views/helpdesk_stage.xml',
        'views/res_config_settings_view.xml',
        'views/website_view.xml',
        'views/expense_view.xml',
        'views/survey_template.xml',
        'views/tracking_template.xml',
        'views/whatsapp_message_template.xml',
        'views/maintenance_request.xml',
        'views/dashboard.xml',
        'views/source_view.xml',
        'views/menu.xml',
        'views/knowledge_views.xml',
        'views/tags_view.xml',
        'views/category_view.xml',
        'views/crm_lead_view.xml',
        'views/helpdesk_ticket_type_views.xml',
        'views/helpdesk_ticket_type_inherit.xml',
        'report/ticket_report_template.xml',
        'report/ticket_report_menu.xml',
        ],
    'assets': {
        'web.assets_frontend': [
            'dev_all_in_one_helpdesk_ent/static/src/js/portal.js',
        ],
        'web.assets_backend': [
            'dev_all_in_one_helpdesk_ent/static/src/js/dashboard.js',
            'dev_all_in_one_helpdesk_ent/static/src/js/chart_chart.js',
            'dev_all_in_one_helpdesk_ent/static/src/css/dashboard_new.css',
            'dev_all_in_one_helpdesk_ent/static/src/css/helpdesk_team.css',
            'dev_all_in_one_helpdesk_ent/static/src/xml/dashboard_templates.xml',
        ]
    },
    'demo':[
        'data/demo_data_view.xml',
     ],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
    #author and support Details
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'https://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':49.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
    'pre_init_hook': 'pre_init_check',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


