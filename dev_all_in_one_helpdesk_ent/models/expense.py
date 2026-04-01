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

class Expense(models.Model):
    _inherit = 'hr.expense'
    
    ticket_count = fields.Integer(string='Ticket Orders', compute='_compute_ticket_count')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket')

    def _compute_ticket_count(self):
        for order in self:
            ticket_ids = self.env['helpdesk.ticket'].search([('expense_id','=',self.id)])
            order.ticket_count = len(ticket_ids)
    
    @api.model
    def create(self,vals):
        expense_id = super(Expense,self).create(vals)
        if expense_id.ticket_id:
            attachment_ids = self.env['ir.attachment'].search([('res_id','=',expense_id.ticket_id.id),
                                                               ('res_model','=','helpdesk.ticket')])
            if attachment_ids:
                for att in attachment_ids:
                    att.copy({'res_model': 'hr.expense','res_id':expense_id.id})
        return expense_id
    
    def create_ticket(self):
        for data in self:
            return {
                'name': _('Ticket'),
                'view_mode': 'form',
                'res_model': 'helpdesk.ticket',
                'view_id': self.env.ref('helpdesk.helpdesk_ticket_view_form').id,
                'type': 'ir.actions.act_window',
                'context': {'default_name': self.name,
                            'default_partner_id': self.employee_id and self.employee_id.user_id and self.employee_id.user_id.partner_id and self.employee_id.user_id.partner_id.id or False,
                            'default_email': self.employee_id and self.employee_id.user_id and self.employee_id.user_id.partner_id and self.employee_id.user_id.partner_id.email or 'None',
                            'default_expense_ticket_flag': True,
                            'default_expense_id': self.id,
                            },
                'target': 'new'
            }
            
    def action_view_ticket(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_tree').read()[0]
        ticket_ids = self.env['helpdesk.ticket'].search([('expense_id','=',self.id)])
        if len(ticket_ids) > 1:
            action['domain'] = [('id', 'in', ticket_ids.ids)]
        elif ticket_ids:
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
            action['res_id'] = ticket_ids.id
        return action
            

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
