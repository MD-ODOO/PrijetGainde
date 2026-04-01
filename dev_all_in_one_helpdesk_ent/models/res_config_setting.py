# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models,api,_
from odoo.exceptions import ValidationError
from datetime import datetime


class Company(models.Model):
    _inherit = 'res.company'
    
    helpdesk_subticket = fields.Boolean('Sub Tickets')
    allow_multi_user = fields.Boolean('Assign multi users')
    notification_user_id = fields.Many2one('res.users',string='Notification User')
    helpdesk_due_reminder = fields.Boolean('Helpdesk Due Reminder')
    reminder_stage_ids = fields.Many2many('helpdesk.stage',string='Reminder Stage')
    draft_stage_id = fields.Many2one('helpdesk.stage', string='Draft Stage')
    done_stage_id = fields.Many2one('helpdesk.stage', string='Done Stage')
    close_stage_id = fields.Many2one('helpdesk.stage', string='Close Stage')
    cancel_stage_id = fields.Many2one('helpdesk.stage', string='Cancel Stage')
    
    def send_helpdesk_due_reminder(self):
        company_ids = self.env['res.company'].sudo().search([('helpdesk_due_reminder', '=', True)])
        for company in company_ids:
            today_date = datetime.now().date()
            ticket_ids = self.env['helpdesk.ticket'].search([('due_date','=',today_date),
                                                                 ('company_id','=',company.id),
                                                                 ('stage_id','in',company.reminder_stage_ids.ids)])
            for ticket in ticket_ids:
                if ticket.user_id:
                    template_id = self.env.ref('dev_all_in_one_helpdesk_ent.dev_helpdesk_tickit_reminder_template')
                    template_id.send_mail(ticket.id, force_send=True)
                
        return True
    
    
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    helpdesk_subticket = fields.Boolean(related='company_id.helpdesk_subticket', readonly=False)
    allow_multi_user = fields.Boolean(related='company_id.allow_multi_user', readonly=False)
    notification_user_id = fields.Many2one('res.users',related='company_id.notification_user_id',readonly=False)
    helpdesk_due_reminder = fields.Boolean(related='company_id.helpdesk_due_reminder', readonly=False)
    reminder_stage_ids = fields.Many2many(related='company_id.reminder_stage_ids', readonly=False, string='Reminder Stage')
    draft_stage_id = fields.Many2one('helpdesk.stage', 
                                             related='company_id.draft_stage_id', 
                                             string='Draft Stage', 
                                             readonly=False)
    done_stage_id = fields.Many2one('helpdesk.stage', 
                                     related='company_id.done_stage_id', 
                                     string='Done Stage', 
                                     readonly=False)
    
    close_stage_id = fields.Many2one('helpdesk.stage', 
                                     related='company_id.close_stage_id', 
                                     string='Close Stage', 
                                     readonly=False)
    
    cancel_stage_id = fields.Many2one('helpdesk.stage', 
                                     related='company_id.cancel_stage_id', 
                                     string='Cancel Stage', 
                                     readonly=False)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
