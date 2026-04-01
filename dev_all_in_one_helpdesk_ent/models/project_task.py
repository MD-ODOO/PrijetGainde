# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#s
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models,api,_
from odoo.exceptions import ValidationError

class project_task(models.Model):
    _inherit = 'project.task'
    
    ticket_id = fields.Many2one('helpdesk.ticket', string='Tiket')
    ticket_count = fields.Integer(string='Ticket Count', compute='_get_ticket_count')
    
    @api.model
    def create(self,vals):
        task_id = super(project_task,self).create(vals)
        if task_id.ticket_id:
            attachment_ids = self.env['ir.attachment'].search([('res_id','=',task_id.ticket_id.id),
                                                               ('res_model','=','helpdesk.ticket')])
            if attachment_ids:
                for att in attachment_ids:
                    att.copy({'res_model': 'project.task','res_id':task_id.id})
        return task_id
    
    def _get_ticket_count(self):
        for ticket in self:
            if ticket.ticket_id:
                ticket.ticket_count = 1
            else:
                ticket.ticket_count = 0

    def action_view_ticket(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_tree').read()[0]
        action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
        action['res_id'] = self.ticket_id.id
        return action
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
